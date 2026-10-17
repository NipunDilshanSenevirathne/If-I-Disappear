"""The model router: every AI step goes through here, so the app runs on the free tier.

Each step (listener, reader, extractor, challenger, grader) has a *chain* of Google
models, best first. For every call the router:

1. answers from the cache if this exact request (same prompt, same file) was
   answered before, so repeated demos don't spend the allowance;
2. checks the visitor's own daily allowance, so one visitor can't use up the
   public demo for everyone;
3. walks the chain and takes the first model that can handle the input (audio,
   image, PDF, text) and still has free-tier allowance, waiting a few seconds
   for a per-minute slot when needed;
4. sends the request; on "slow down" (429), "model not found" or a server error
   it moves to the next model; on success it checks the reply against the
   expected JSON schema before anyone uses it;
5. records which model answered and why others were skipped, for the
   "How it was worked out" screen and the live AI allowance panel.

If every model is out of allowance, it raises AIUnavailable with a plain
message. The workflows then fall back to code (the engine runs without the AI
review; practice uses the keyword grader) and say so.

Chain entries look like "gemini-3.8-flash:keep=8": use this model only while
more than 8 of today's requests are left (the rest are kept for the AI
reviewer, which runs less often but benefits most from the strongest model).
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import re
import time
from collections import OrderedDict, defaultdict
from collections.abc import AsyncGenerator, Iterator
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache

from google.adk.models import LlmRequest, LlmResponse
from google.adk.models.google_llm import Gemini
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from ..config import get_settings
from .quota import QuotaLedger, label, pacific_day, parse_limits

log = logging.getLogger("ai.router")

# ---------------------------------------------------------------------- what each model can read

CAPABILITIES: dict[str, set[str]] = {
    "gemini-3.8-flash": {"text", "image", "audio", "pdf"},
    "gemini-3.6-flash": {"text", "image", "audio", "pdf"},
    "gemini-3.5-flash-lite": {"text", "image", "audio", "pdf"},
    "gemini-3.1-flash-lite": {"text", "image", "audio", "pdf"},
    "gemma-4-31b-it": {"text", "image"},
    "gemma-4-26b-a4b-it": {"text", "image"},
}

DEFAULT_CHAINS: dict[str, str] = {
    # Audio can only go to Gemini, so voice notes may use every last Flash-Lite request.
    "listener": "gemini-3.8-flash:keep=8, gemini-3.5-flash-lite, gemini-3.1-flash-lite",
    # Text and images can also go to Gemma; they leave the last 200 requests of each
    # Flash-Lite model to voice notes and PDFs, which only Gemini can read.
    "reader": "gemini-3.8-flash:keep=8, gemini-3.5-flash-lite:keep=200, gemini-3.1-flash-lite:keep=200, gemma-4-31b-it",
    "extractor": "gemini-3.8-flash:keep=8, gemini-3.5-flash-lite:keep=200, gemini-3.1-flash-lite:keep=200, gemma-4-31b-it",
    # The reviewer runs least often and gains most from the strongest model.
    "challenger": "gemini-3.8-flash, gemini-3.5-flash-lite:keep=200, gemini-3.1-flash-lite:keep=200, gemma-4-31b-it",
    "grader": "gemini-3.5-flash-lite:keep=200, gemini-3.1-flash-lite:keep=200, gemma-4-31b-it, gemini-3.8-flash:keep=8",
}


@dataclass(frozen=True)
class Link:
    model: str
    keep: int = 0  # skip this model when this many (or fewer) requests are left today


def parse_chain(text: str) -> list[Link]:
    links: list[Link] = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        model, _, opts = item.partition(":")
        keep = 0
        m = re.search(r"keep=(\d+)", opts)
        if m:
            keep = int(m.group(1))
        links.append(Link(model.strip(), keep))
    return links


def chain_for(role: str) -> list[Link]:
    s = get_settings()
    text = s.ai_chains.get(role) or DEFAULT_CHAINS.get(role) or DEFAULT_CHAINS["extractor"]
    links = parse_chain(text)
    if s.model_override:  # MODEL_REASON (older setting): put that model first everywhere
        links = [Link(s.model_override)] + [link for link in links if link.model != s.model_override]
    return links


def is_gemma(model: str) -> bool:
    return model.startswith("gemma")


# ---------------------------------------------------------------------- shared state


@lru_cache
def ledger() -> QuotaLedger:
    s = get_settings()
    return QuotaLedger(parse_limits(s.quota_tier, s.quota_limits), reserve=s.quota_reserve)


class AIUnavailable(RuntimeError):
    """No model could answer. The message is shown to the person as it is."""


class ResponseCache:
    """Remembers answers to identical requests for a few days (in memory)."""

    def __init__(self, size: int = 400, ttl_seconds: float = 3 * 86400) -> None:
        self.size = size
        self.ttl = ttl_seconds
        self.items: OrderedDict[str, tuple[float, str, str]] = OrderedDict()

    def get(self, key: str) -> tuple[str, str] | None:
        hit = self.items.get(key)
        if hit is None:
            return None
        at, model, text = hit
        if time.time() - at > self.ttl:
            self.items.pop(key, None)
            return None
        self.items.move_to_end(key)
        return model, text

    def put(self, key: str, model: str, text: str) -> None:
        self.items[key] = (time.time(), model, text)
        self.items.move_to_end(key)
        while len(self.items) > self.size:
            self.items.popitem(last=False)

    def clear(self) -> None:
        self.items.clear()


cache = ResponseCache()

# per-visitor daily allowance: (pacific day, visitor) -> calls
_visitor_calls: dict[tuple[str, str], int] = defaultdict(int)

VISITOR: ContextVar[str | None] = ContextVar("ai_visitor", default=None)
CALLS: ContextVar[list[dict] | None] = ContextVar("ai_calls", default=None)


@contextlib.contextmanager
def ai_scope(visitor: str | None) -> Iterator[list[dict]]:
    """Attribute the model calls made inside this block to a visitor, and collect them."""
    calls: list[dict] = []
    t1 = VISITOR.set(visitor)
    t2 = CALLS.set(calls)
    try:
        yield calls
    finally:
        VISITOR.reset(t1)
        CALLS.reset(t2)


def visitor_usage(visitor: str | None) -> dict:
    s = get_settings()
    used = _visitor_calls.get((pacific_day(), visitor or ""), 0)
    limit = s.ai_calls_per_visitor or None
    return {"used_today": used, "limit_today": limit, "left_today": None if limit is None else max(0, limit - used)}


def _note_call(entry: dict) -> None:
    calls = CALLS.get()
    if calls is not None:
        calls.append(entry)


# ---------------------------------------------------------------------- request helpers


def _media(req: LlmRequest) -> list[types.Part]:
    out = []
    for content in req.contents or []:
        for part in content.parts or []:
            if part.inline_data is not None:
                out.append(part)
    return out


def needs_of(req: LlmRequest) -> set[str]:
    need = {"text"}
    for part in _media(req):
        mime = (part.inline_data.mime_type or "").lower()
        if mime.startswith("audio/") or mime.startswith("video/"):
            need.add("audio")
        elif mime == "application/pdf":
            need.add("pdf")
        elif mime.startswith("image/"):
            need.add("image")
        else:
            need.add("pdf")
    return need


def _instruction_text(req: LlmRequest) -> str:
    si = req.config.system_instruction if req.config else None
    if si is None:
        return ""
    if isinstance(si, str):
        return si
    if isinstance(si, types.Content):
        return "\n".join(p.text or "" for p in si.parts or [])
    return str(si)


def cache_key(role: str, req: LlmRequest) -> str:
    texts: list[str] = []
    blobs: list[str] = []
    for content in req.contents or []:
        for part in content.parts or []:
            if part.text:
                texts.append(part.text)
            elif part.inline_data is not None and part.inline_data.data:
                blobs.append(hashlib.sha256(part.inline_data.data).hexdigest())
    schema = req.config.response_schema if req.config else None
    schema_name = getattr(schema, "__name__", str(schema))
    payload = json.dumps([role, schema_name, _instruction_text(req), texts, blobs], ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def estimate_tokens(req: LlmRequest) -> int:
    chars = len(_instruction_text(req))
    tokens = 0
    for content in req.contents or []:
        for part in content.parts or []:
            if part.text:
                chars += len(part.text)
            elif part.inline_data is not None:
                size = len(part.inline_data.data or b"")
                mime = part.inline_data.mime_type or ""
                if mime.startswith("image/"):
                    tokens += 1100
                elif mime.startswith("audio/"):
                    tokens += max(200, size // 500)  # ~32 tokens per second of compressed speech
                else:
                    tokens += max(800, size // 300)
    return tokens + chars // 4


def _schema(req: LlmRequest) -> type[BaseModel] | None:
    schema = req.config.response_schema if req.config else None
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        return schema
    return None


def adapt_for(model: str, req: LlmRequest) -> LlmRequest:
    """A copy of the request for one model. Gemma gets the schema as an instruction
    instead of JSON mode, and no thinking settings."""
    r = req.model_copy(deep=True)
    r.model = model
    if is_gemma(model) and r.config is not None:
        schema = _schema(req)
        r.config.response_schema = None
        r.config.response_mime_type = None
        r.config.thinking_config = None
        if schema is not None:
            js = json.dumps(schema.model_json_schema(), separators=(",", ":"))
            r.config.system_instruction = (
                _instruction_text(req)
                + "\n\nReply with one JSON object only: no prose, no code fences. It must match this JSON Schema:\n"
                + js
            )
    return r


def extract_json(text: str) -> str:
    """Take the JSON object out of a reply that may be wrapped in prose or code fences."""
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", t, re.DOTALL)
    if fence:
        t = fence.group(1).strip()
    if t.startswith("{") and t.endswith("}"):
        return t
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end > start:
        return t[start : end + 1]
    return t


def _reply_text(resp: LlmResponse) -> str:
    if resp.content is None:
        return ""
    return "".join(p.text or "" for p in resp.content.parts or [] if p.text and not getattr(p, "thought", False))


def _retry_after(exc: errors.APIError) -> tuple[float | None, bool]:
    """(seconds to wait, is this the daily allowance) from a 429 error."""
    text = json.dumps(exc.details, default=str) if exc.details is not None else str(exc)
    daily = bool(re.search(r"PerDay|per day|daily", text, re.IGNORECASE))
    m = re.search(r'retryDelay"?\s*[:=]\s*"?(\d+(?:\.\d+)?)s', text)
    return (float(m.group(1)) if m else None), daily


def _plain(reason: str) -> str:
    return {
        "daily allowance used up": "used up for today",
        "requests-per-minute limit": "busy this minute",
        "tokens-per-minute limit": "busy this minute",
    }.get(reason, reason)


# ---------------------------------------------------------------------- the call


async def route_call(base: Gemini, role: str, llm_request: LlmRequest, stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
    s = get_settings()
    q = ledger()
    started = time.perf_counter()
    key = cache_key(role, llm_request)
    schema = _schema(llm_request)

    hit = cache.get(key)
    if hit is not None:
        model, text = hit
        q.record_cached()
        _note_call({"role": role, "model": model, "label": label(model), "cached": True, "ok": True, "ms": 0, "skipped": []})
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))
        return

    visitor = VISITOR.get()
    if s.ai_calls_per_visitor and visitor:
        day_key = (pacific_day(), visitor)
        if _visitor_calls[day_key] >= s.ai_calls_per_visitor:
            raise AIUnavailable(
                "You've used this demo's AI allowance for today. Everything else still works, "
                "and you can type facts in yourself. It resets at midnight Pacific time."
            )

    need = needs_of(llm_request)
    est = estimate_tokens(llm_request)
    skipped: list[dict] = []
    links = chain_for(role)
    able = [link.model for link in links if need <= CAPABILITIES.get(link.model, {"text"})]
    for link in links:
        model = link.model
        caps = CAPABILITIES.get(model, {"text"})
        if not need <= caps:
            skipped.append({"model": model, "label": label(model), "why": "can't read this kind of file"})
            continue
        left = q.snapshot([model])["models"][0]["left_today"]
        if link.keep and left is not None and left <= link.keep:
            skipped.append({"model": model, "label": label(model), "why": "kept for the AI reviewer"})
            continue
        ok, why = await q.acquire(model, est, max_wait=s.ai_max_wait)
        if not ok:
            skipped.append({"model": model, "label": label(model), "why": _plain(why)})
            continue
        request = adapt_for(model, llm_request)
        # A model that is slow today shouldn't hold everything up: when another model could
        # still take this request, give this one a shorter try (AI_TRY_TIMEOUT).
        later = able.index(model) < len(able) - 1 if model in able else False
        limit = min(s.ai_timeout, s.ai_try_timeout) if later else s.ai_timeout
        t0 = time.perf_counter()
        try:
            final: LlmResponse | None = None
            async with asyncio.timeout(limit):
                async for resp in Gemini.generate_content_async(base, request, stream=False):
                    final = resp
            text = _reply_text(final) if final is not None else ""
            if not text.strip():
                raise ValueError("empty reply")
            if is_gemma(model) and schema is not None:
                text = extract_json(text)
            if schema is not None:
                schema.model_validate_json(text)  # never pass on a reply that doesn't fit the schema
        except errors.APIError as exc:
            code = getattr(exc, "code", None)
            if code == 429:
                retry, daily = _retry_after(exc)
                q.record_rejected(model, retry, daily)
                skipped.append(
                    {"model": model, "label": label(model), "why": "used up for today" if daily else "Google asked us to slow down"}
                )
            elif code in (403, 404):
                q.record_failed(model)
                q.disable(model, 3600, "not available to this key")
                skipped.append({"model": model, "label": label(model), "why": "not available to this key"})
            elif code == 400:
                # this request, not the model: another model may take it (no cool-down)
                q.record_failed(model)
                skipped.append({"model": model, "label": label(model), "why": "couldn't take this request"})
            else:
                q.record_failed(model)
                q.disable(model, 20, "Google had a problem")
                skipped.append({"model": model, "label": label(model), "why": "Google had a problem"})
            log.warning("model %s failed for %s: %s", model, role, str(exc)[:300])
            continue
        except (TimeoutError, ValueError, ValidationError) as exc:
            q.record_failed(model)
            if isinstance(exc, TimeoutError):
                # Google is slow on this model right now: let the next few calls go elsewhere.
                q.disable(model, 120, "slow right now")
                skipped.append({"model": model, "label": label(model), "why": f"took longer than {round(limit)} s"})
                log.warning("model %s took longer than %ss for %s; trying the next model", model, round(limit), role)
            else:
                skipped.append({"model": model, "label": label(model), "why": "answer didn't fit the expected form"})
                log.warning("model %s gave an unusable reply for %s: %s", model, role, str(exc)[:300])
            continue

        usage = final.usage_metadata if final is not None else None
        q.record_ok(model, getattr(usage, "prompt_token_count", 0) or 0, getattr(usage, "candidates_token_count", 0) or 0)
        if visitor and s.ai_calls_per_visitor:
            _visitor_calls[(pacific_day(), visitor)] += 1
        cache.put(key, model, text)
        _note_call(
            {
                "role": role,
                "model": model,
                "label": label(model),
                "cached": False,
                "ok": True,
                "ms": round((time.perf_counter() - t0) * 1000),
                "skipped": skipped,
            }
        )
        out = final.model_copy(update={"content": types.Content(role="model", parts=[types.Part(text=text)])})
        yield out
        return

    _note_call(
        {
            "role": role,
            "model": None,
            "label": None,
            "cached": False,
            "ok": False,
            "ms": round((time.perf_counter() - started) * 1000),
            "skipped": skipped,
        }
    )
    reasons = "; ".join(f"{x['label']}: {x['why']}" for x in skipped) or "no model is configured"
    raise AIUnavailable(f"No AI model could take this right now ({reasons}). The rest of the app keeps working.")


class RoutedGemini(Gemini):
    """An ADK model that sends each request through the router."""

    role: str = "extractor"

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
        async for resp in route_call(self, self.role, llm_request, stream):
            yield resp


def usage_snapshot(visitor: str | None = None) -> dict:
    s = get_settings()
    q = ledger()
    models = []
    for link_model in _all_models():
        models.append(link_model)
    snap = q.snapshot(models)
    snap["tier"] = s.quota_tier
    snap["mode"] = s.ai_mode
    snap["live_model"] = {"model": s.model_live, "label": label(s.model_live)}
    snap["chains"] = {
        role: [{"model": link.model, "label": label(link.model), "keep": link.keep} for link in chain_for(role)] for role in DEFAULT_CHAINS
    }
    snap["visitor"] = visitor_usage(visitor)
    snap["generated"] = datetime.now(UTC).isoformat()
    return snap


def _all_models() -> list[str]:
    seen: list[str] = []
    for role in DEFAULT_CHAINS:
        for link in chain_for(role):
            if link.model not in seen:
                seen.append(link.model)
    return seen


def reset_for_tests() -> None:
    ledger.cache_clear()
    cache.clear()
    _visitor_calls.clear()


__all__ = [
    "AIUnavailable",
    "CALLS",
    "RoutedGemini",
    "ai_scope",
    "cache",
    "chain_for",
    "ledger",
    "reset_for_tests",
    "route_call",
    "usage_snapshot",
    "visitor_usage",
]
