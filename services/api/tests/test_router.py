"""The free-tier model router: quotas, fallbacks, Gemma JSON, the cache and visitor limits.

No network: Gemini.generate_content_async is replaced by a fake that answers
(or fails) per model, the way Google's API does.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import pytest
from google.adk.models import LlmRequest, LlmResponse
from google.adk.models.google_llm import Gemini
from google.genai import errors, types
from pydantic import BaseModel

from app.ai import router as r
from app.ai.quota import Limit, QuotaLedger, next_reset, pacific_day, parse_limits
from app.config import get_settings


class Answer(BaseModel):
    text: str
    n: int = 0


def run(coro):
    return asyncio.run(coro)


def request(text: str = "hello", media: bytes | None = None, mime: str = "audio/webm") -> LlmRequest:
    parts = [types.Part(text=text)]
    if media is not None:
        parts.append(types.Part(inline_data=types.Blob(mime_type=mime, data=media)))
    req = LlmRequest(
        model="placeholder",
        contents=[types.Content(role="user", parts=parts)],
        config=types.GenerateContentConfig(system_instruction="Be exact."),
    )
    req.set_output_schema(Answer)
    return req


def quota_error(daily: bool = False, delay: str = "7s") -> errors.ClientError:
    quota_id = "GenerateRequestsPerDayPerProjectPerModel-FreeTier" if daily else "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"
    return errors.ClientError(
        429,
        {
            "error": {
                "code": 429,
                "message": "You exceeded your current quota.",
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [{"quotaId": quota_id}]},
                    {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": delay},
                ],
            }
        },
    )


@pytest.fixture
def fake(monkeypatch):
    """Configure live mode with small chains and a scripted fake model."""
    monkeypatch.setenv("AI_MODE", "live")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("AI_CHAIN_EXTRACTOR", "gemini-3.8-flash:keep=2, gemini-3.5-flash-lite, gemma-4-31b-it")
    monkeypatch.setenv("AI_CHAIN_LISTENER", "gemini-3.5-flash-lite, gemma-4-31b-it, gemini-3.1-flash-lite")
    monkeypatch.setenv("AI_MAX_WAIT", "0")
    monkeypatch.delenv("AI_CALLS_PER_VISITOR", raising=False)
    get_settings.cache_clear()
    r.reset_for_tests()
    script: dict[str, object] = {}
    seen: list[LlmRequest] = []

    async def generate(self, llm_request: LlmRequest, stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
        seen.append(llm_request)
        what = script.get(llm_request.model, '{"text": "ok"}')
        if isinstance(what, Exception):
            raise what
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=str(what))]),
            usage_metadata=types.GenerateContentResponseUsageMetadata(prompt_token_count=40, candidates_token_count=10),
        )

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    yield script, seen
    get_settings.cache_clear()
    r.reset_for_tests()


def call(role: str, req: LlmRequest, visitor: str | None = None) -> tuple[str, list[dict]]:
    async def go():
        model = r.RoutedGemini(model="gemini-3.5-flash-lite", role=role)
        with r.ai_scope(visitor) as calls:
            out = [resp async for resp in model.generate_content_async(req)]
        return out[-1].content.parts[0].text, calls

    return run(go())


# ---------------------------------------------------------------------- the ledger


def test_chain_parsing():
    links = r.parse_chain("gemini-3.8-flash:keep=8, gemini-3.5-flash-lite ,, gemma-4-31b-it")
    assert [(link.model, link.keep) for link in links] == [("gemini-3.8-flash", 8), ("gemini-3.5-flash-lite", 0), ("gemma-4-31b-it", 0)]


def test_free_tier_limits_and_overrides():
    free = parse_limits("free", None)
    assert free["gemini-3.8-flash"] == Limit(rpm=5, tpm=250_000, rpd=20)
    assert free["gemini-3.5-flash-lite"].rpd == 500
    assert free["gemma-4-31b-it"].rpd == 14_400
    assert free["gemini-3.8-live"].rpd is None
    paid = parse_limits("paid", '{"gemini-3.8-flash": {"rpm": 1000}}')
    assert paid["gemini-3.5-flash-lite"] == Limit() and paid["gemini-3.8-flash"].rpm == 1000


def test_ledger_waits_for_a_per_minute_slot_then_stops_at_the_daily_cap():
    now = [1_800_000_000.0]
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)
        now[0] += seconds

    q = QuotaLedger({"m": Limit(rpm=2, rpd=3)}, clock=lambda: now[0], sleep=sleep)

    async def go():
        a = await q.acquire("m", max_wait=0)
        b = await q.acquire("m", max_wait=0)
        c = await q.acquire("m", max_wait=0)  # third in the same minute: no waiting allowed
        d = await q.acquire("m", max_wait=90)  # waits for the window to free up
        e = await q.acquire("m", max_wait=90)  # daily cap reached: refuses without waiting
        return a, b, c, d, e

    a, b, c, d, e = run(go())
    assert a == (True, "") and b == (True, "")
    assert c == (False, "requests-per-minute limit")
    assert d == (True, "") and slept and 59 < slept[0] < 61
    assert e == (False, "daily allowance used up")
    row = q.snapshot(["m"])["models"][0]
    assert row["used_today"] == 3 and row["left_today"] == 0


def test_ledger_reserve_rejections_and_new_day():
    now = [1_800_000_000.0]
    q = QuotaLedger({"m": Limit(rpd=100)}, reserve=0.05, clock=lambda: now[0])
    assert q.daily_cap("m") == 95
    run(q.acquire("m"))
    q.record_rejected("m", retry_after=12)
    ok, wait, reason = q.check("m")
    assert not ok and 11 < wait <= 12 and "slow down" in reason
    assert q.snapshot(["m"])["models"][0]["used_today"] == 0  # a 429 doesn't use the allowance
    q.record_rejected("m", daily=True)
    assert q.check("m")[2] == "daily allowance used up"
    now[0] = next_reset().timestamp() + 3600 * 24 * 2  # a later quota day
    assert q.check("m")[0] is True


def test_ledger_survives_a_restart():
    now = [1_800_000_000.0]
    q = QuotaLedger({"m": Limit(rpd=10)}, clock=lambda: now[0])
    run(q.acquire("m"))
    q.record_ok("m", 100, 20)
    saved = q.dump()
    fresh = QuotaLedger({"m": Limit(rpd=10)}, clock=lambda: now[0])
    fresh.load(saved)
    assert fresh.snapshot(["m"])["models"][0]["used_today"] == 1
    other_day = dict(saved, day="1999-01-01")
    fresh2 = QuotaLedger({"m": Limit(rpd=10)}, clock=lambda: now[0])
    fresh2.load(other_day)
    assert fresh2.snapshot(["m"])["models"][0]["used_today"] == 0
    assert pacific_day() == pacific_day()


# ---------------------------------------------------------------------- the router


def test_best_model_first_and_trace(fake):
    script, seen = fake
    script["gemini-3.8-flash"] = '{"text": "from flash", "n": 1}'
    text, calls = call("extractor", request())
    assert '"from flash"' in text
    assert calls[-1]["model"] == "gemini-3.8-flash" and calls[-1]["label"] == "Gemini 3.8 Flash"
    assert seen[-1].config.response_schema is Answer  # Gemini keeps JSON mode


def test_falls_back_on_quota_and_remembers_it(fake):
    script, seen = fake
    script["gemini-3.8-flash"] = quota_error(daily=True)
    text, calls = call("extractor", request("first"))
    assert calls[-1]["model"] == "gemini-3.5-flash-lite"
    assert calls[-1]["skipped"][0] == {"model": "gemini-3.8-flash", "label": "Gemini 3.8 Flash", "why": "used up for today"}
    # the next call doesn't even try the exhausted model
    before = len(seen)
    call("extractor", request("second"))
    assert [q.model for q in seen[before:]] == ["gemini-3.5-flash-lite"]


def test_keep_floor_saves_the_strong_model_for_the_reviewer(fake):
    script, seen = fake
    q = r.ledger()
    q.limits["gemini-3.8-flash"] = Limit(rpm=100, rpd=4)  # 3 usable a day (5% reserve), keep 2 for the reviewer
    call("extractor", request("a"))
    assert seen[-1].model == "gemini-3.8-flash"
    _, calls = call("extractor", request("b"))
    assert seen[-1].model == "gemini-3.5-flash-lite"
    assert calls[-1]["skipped"][0]["why"] == "kept for the AI reviewer"


def test_gemma_gets_the_schema_as_text_and_json_is_unwrapped(fake):
    script, seen = fake
    script["gemini-3.8-flash"] = quota_error()
    script["gemini-3.5-flash-lite"] = errors.ServerError(503, {"error": {"code": 503, "message": "overloaded", "status": "UNAVAILABLE"}})
    script["gemma-4-31b-it"] = 'Sure! Here it is:\n```json\n{"text": "from gemma", "n": 2}\n```'
    text, calls = call("extractor", request())
    assert text == '{"text": "from gemma", "n": 2}'
    gemma_req = seen[-1]
    assert gemma_req.model == "gemma-4-31b-it"
    assert gemma_req.config.response_schema is None and gemma_req.config.response_mime_type is None
    assert "JSON Schema" in gemma_req.config.system_instruction and "Be exact." in gemma_req.config.system_instruction
    assert [s["why"] for s in calls[-1]["skipped"]] == ["Google asked us to slow down", "Google had a problem"]


def test_a_reply_that_breaks_the_schema_is_never_passed_on(fake):
    script, _ = fake
    script["gemini-3.8-flash"] = '{"oops": true}'
    script["gemini-3.5-flash-lite"] = "not json at all"
    script["gemma-4-31b-it"] = '{"text": "valid"}'
    text, calls = call("extractor", request())
    assert text == '{"text": "valid"}'
    assert [s["why"] for s in calls[-1]["skipped"]] == ["answer didn't fit the expected form"] * 2


def test_audio_skips_models_that_cannot_hear(fake):
    script, seen = fake
    script["gemini-3.5-flash-lite"] = quota_error(daily=True)
    text, calls = call("listener", request("listen", media=b"\x1aE\xdf\xa3" + b"0" * 100))
    assert seen[-1].model == "gemini-3.1-flash-lite"
    assert {"model": "gemma-4-31b-it", "label": "Gemma 4 31B", "why": "can't read this kind of file"} in calls[-1]["skipped"]


def test_same_request_twice_is_answered_from_the_cache(fake):
    script, seen = fake
    call("extractor", request("same"))
    n = len(seen)
    text, calls = call("extractor", request("same"))
    assert len(seen) == n and calls[-1]["cached"] is True
    assert r.ledger().cached_hits == 1


def test_everything_unavailable_raises_a_plain_message(fake):
    script, _ = fake
    for m in ("gemini-3.8-flash", "gemini-3.5-flash-lite", "gemma-4-31b-it"):
        script[m] = quota_error(daily=True)
    with pytest.raises(r.AIUnavailable) as exc:
        call("extractor", request())
    assert "No AI model could take this right now" in str(exc.value)
    assert "Gemma 4 31B: used up for today" in str(exc.value)


def test_unknown_model_is_set_aside(fake):
    script, seen = fake
    script["gemini-3.8-flash"] = errors.ClientError(
        404, {"error": {"code": 404, "message": "models/gemini-3.8-flash is not found", "status": "NOT_FOUND"}}
    )
    call("extractor", request("x"))
    call("extractor", request("y"))
    assert [q.model for q in seen] == ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.5-flash-lite"]


def test_visitor_allowance(fake, monkeypatch):
    monkeypatch.setenv("AI_CALLS_PER_VISITOR", "2")
    get_settings.cache_clear()
    call("extractor", request("1"), visitor="v-1")
    call("extractor", request("2"), visitor="v-1")
    with pytest.raises(r.AIUnavailable) as exc:
        call("extractor", request("3"), visitor="v-1")
    assert "allowance" in str(exc.value)
    call("extractor", request("3"), visitor="v-2")  # someone else is unaffected
    usage = r.usage_snapshot("v-1")
    assert usage["visitor"] == {"used_today": 2, "limit_today": 2, "left_today": 0}
    assert {m["model"] for m in usage["models"]} >= {"gemini-3.8-flash", "gemini-3.5-flash-lite", "gemma-4-31b-it"}
