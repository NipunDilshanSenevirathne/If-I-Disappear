"""Section 6: a day on the free tier (simulated traffic, no network).

The router (services/api/app/ai/router.py) is run against the free-tier limits
in app/ai/quota.py with a simulated clock and a stand-in model that always
answers instantly. That isolates the question this section asks: with only a
free Gemini API key, how much of a day's traffic gets an answer, from which
model, and how long people wait for a per-minute slot? It does not measure
answer quality or Google's real latency; the live section does that.
"""

from __future__ import annotations

import asyncio
import random
from collections import Counter
from collections.abc import AsyncGenerator

from .common import Metric, Section, ratio

# One visit, as the app makes model calls: a voice note (listen + extract), a photo
# (read + extract), one "Check again with AI" (review) and two typed practice checks.
VISIT = [
    ("listener", "audio/webm"),
    ("extractor", None),
    ("reader", "image/jpeg"),
    ("extractor", None),
    ("challenger", None),
    ("grader", None),
    ("grader", None),
]


def _simulate(visitors: int, spread_minutes: float, *, chains: dict[str, str] | None = None, seed: int = 7) -> dict:
    from app.ai import router as r
    from app.ai.quota import FREE_TIER, QuotaLedger
    from app.config import get_settings
    from google.adk.models import LlmRequest, LlmResponse
    from google.adk.models.google_llm import Gemini
    from google.genai import types
    from pydantic import BaseModel

    class Out(BaseModel):
        ok: bool = True

    now = [1_800_000_000.0]  # a fixed moment; the day boundary doesn't matter here

    async def sleep(seconds: float) -> None:
        now[0] += seconds

    ledger = QuotaLedger(dict(FREE_TIER), reserve=get_settings().quota_reserve, clock=lambda: now[0], sleep=sleep)
    answered: Counter[str] = Counter()
    first_choice: Counter[str] = Counter()
    refused = 0
    audio_refused = 0
    waits: list[float] = []

    async def fake(self, llm_request: LlmRequest, stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text='{"ok": true}')]))

    rng = random.Random(seed)
    calls: list[tuple[float, int, str, str | None]] = []
    for v in range(visitors):
        start = rng.uniform(0, spread_minutes * 60)
        for i, (role, mime) in enumerate(VISIT):
            calls.append((start + i * rng.uniform(20, 90), v, role, mime))
    calls.sort()

    original_ledger, original_generate = r.ledger, Gemini.generate_content_async
    # The simulation describes the shipped settings, whatever this shell has set
    # (AI_MAX_WAIT or AI_CHAIN_* overrides used for a live run don't leak in).
    saved_chains = dict(get_settings().ai_chains)
    saved_wait = get_settings().ai_max_wait
    r.ledger = lambda: ledger  # type: ignore[assignment]
    Gemini.generate_content_async = fake  # type: ignore[method-assign]
    get_settings().ai_max_wait = 20.0
    get_settings().ai_chains.clear()
    get_settings().ai_chains.update(chains or {})
    try:

        async def go():
            nonlocal refused, audio_refused
            base = r.RoutedGemini(model="gemini-3.5-flash-lite", role="extractor")
            for n, (at, v, role, mime) in enumerate(calls):
                now[0] = max(now[0], 1_800_000_000.0 + at)
                parts = [types.Part(text=f"visit {v} call {n} {role}")]
                if mime:
                    parts.append(types.Part(inline_data=types.Blob(mime_type=mime, data=bytes([n % 251]) * 2048)))
                req = LlmRequest(model="x", contents=[types.Content(role="user", parts=parts)], config=types.GenerateContentConfig())
                req.set_output_schema(Out)
                base.role = role
                before = now[0]
                with r.ai_scope(None) as made:
                    try:
                        async for _ in base.generate_content_async(req):
                            pass
                    except r.AIUnavailable:
                        refused += 1
                        audio_refused += bool(mime and mime.startswith("audio"))
                        continue
                waits.append(now[0] - before)
                model = made[-1]["model"]
                answered[model] += 1
                if model == r.chain_for(role)[0].model:
                    first_choice[role] += 1

        asyncio.run(go())
    finally:
        r.ledger = original_ledger  # type: ignore[assignment]
        Gemini.generate_content_async = original_generate  # type: ignore[method-assign]
        get_settings().ai_chains.clear()
        get_settings().ai_chains.update(saved_chains)
        get_settings().ai_max_wait = saved_wait
        r.cache.clear()
    return {
        "calls": len(calls),
        "answered": sum(answered.values()),
        "refused": refused,
        "by_model": dict(answered),
        "first_choice": sum(first_choice.values()),
        "gemini": sum(n for m, n in answered.items() if m.startswith("gemini")),
        "audio_calls": sum(1 for c in calls if c[3] and c[3].startswith("audio")),
        "audio_refused": audio_refused,
        "max_wait": max(waits) if waits else 0.0,
        "waited": sum(1 for w in waits if w > 0.5),
    }


def router_section() -> Section:
    from app.ai.quota import label

    s = Section(
        "router",
        "A day on the free tier (simulated)",
        "Simulated traffic through the real model router, against Google's free-tier limits for one project (Gemini 3.8 Flash "
        "5 a minute / 20 a day; 3.5 and 3.1 Flash-Lite 15 a minute / 500 a day; Gemma 4 31B 30 a minute / 14,400 a day; 5% of "
        "each day kept in reserve). A visit is one voice note, one photo, one AI review and two practice checks: 7 model calls. "
        "The stand-in model answers instantly, so this measures allowance and waiting, not answer quality or Google's speed.",
    )
    day = _simulate(60, 9 * 60)
    busy = _simulate(400, 12 * 60)
    rush = _simulate(30, 5)
    single = _simulate(60, 9 * 60, chains={k: "gemini-3.8-flash" for k in ("listener", "reader", "extractor", "challenger", "grader")})

    s.metrics.append(ratio("Judging day, 60 visits over 9 hours: calls answered", day["answered"], day["calls"], target_pct=100))
    s.metrics.append(ratio("Same day: answered by a Gemini model (native JSON mode, no fallback to Gemma)", day["gemini"], day["calls"]))
    s.metrics.append(ratio("Busy day, 400 visits over 12 hours: calls answered", busy["answered"], busy["calls"], target_pct=100))
    s.metrics.append(
        ratio(
            "Busy day: voice notes heard (only Gemini models take audio)",
            busy["audio_calls"] - busy["audio_refused"],
            busy["audio_calls"],
            target_pct=100,
        )
    )
    s.metrics.append(ratio("Rush, 30 visits in 5 minutes: calls answered", rush["answered"], rush["calls"], target_pct=100))
    s.metrics.append(
        Metric(
            "Rush: longest wait for a free slot",
            f"{rush['max_wait']:.0f} s",
            "≤ 20 s",
            "pass" if rush["max_wait"] <= 20.5 else "fail",
            f"{rush['waited']} of {rush['answered']} calls waited at all",
            rush["max_wait"],
        )
    )
    s.metrics.append(
        ratio(
            "Baseline, one model only (Gemini 3.8 Flash), judging day: calls answered",
            single["answered"],
            single["calls"],
            note="What a single free-tier model would manage on the same day.",
        )
    )
    for name, run in (("Judging day", day), ("Busy day", busy), ("Rush", rush)):
        parts = ", ".join(f"{label(m)} {n}" for m, n in sorted(run["by_model"].items(), key=lambda kv: -kv[1]))
        s.details.append(f"- {name}: {run['answered']} of {run['calls']} answered ({parts}); {run['refused']} refused.")
    return s
