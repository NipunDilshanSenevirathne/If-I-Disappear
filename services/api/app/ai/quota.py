"""The free-tier ledger: how much of each Gemini/Gemma model's allowance is left.

Google's free tier limits every model per project in three ways:

  RPM  requests per minute
  TPM  input tokens per minute
  RPD  requests per day, reset at midnight Pacific time

The ledger counts what this server has sent, waits for a free slot when a
per-minute limit is reached, and refuses (so the router can move on to the next
model) when a daily allowance is used up or Google says "slow down". It never
guesses quietly: every refusal has a reason the interface can show.

The numbers below are the free-tier limits shown in Google AI Studio for a
project in October 2026 (aistudio.google.com/rate-limit). Google can change
them; set QUOTA_LIMITS to override any model, or QUOTA_TIER=paid to stop
counting against these limits.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

PACIFIC = ZoneInfo("America/Los_Angeles")


@dataclass(frozen=True)
class Limit:
    rpm: int | None = None  # None means no limit
    tpm: int | None = None
    rpd: int | None = None


FREE_TIER: dict[str, Limit] = {
    "gemini-3.8-flash": Limit(rpm=5, tpm=250_000, rpd=20),
    "gemini-3.5-flash-lite": Limit(rpm=15, tpm=250_000, rpd=500),
    "gemini-3.1-flash-lite": Limit(rpm=15, tpm=250_000, rpd=500),
    "gemma-4-31b-it": Limit(rpm=30, tpm=16_000, rpd=14_400),
    "gemma-4-26b-a4b-it": Limit(rpm=30, tpm=16_000, rpd=14_400),
    "gemini-3.8-live": Limit(rpm=None, tpm=65_000, rpd=None),
}

LABELS: dict[str, str] = {
    "gemini-3.8-flash": "Gemini 3.8 Flash",
    "gemini-3.5-flash-lite": "Gemini 3.5 Flash-Lite",
    "gemini-3.1-flash-lite": "Gemini 3.1 Flash-Lite",
    "gemma-4-31b-it": "Gemma 4 31B",
    "gemma-4-26b-a4b-it": "Gemma 4 26B",
    "gemini-3.8-live": "Gemini 3.8 Live",
}


def label(model: str) -> str:
    return LABELS.get(model, model)


def pacific_day(at: datetime | None = None) -> str:
    """The quota day a moment belongs to (Google resets daily limits at midnight Pacific)."""
    at = at or datetime.now(UTC)
    return at.astimezone(PACIFIC).date().isoformat()


def next_reset(at: datetime | None = None) -> datetime:
    """The next midnight Pacific time, in UTC."""
    at = (at or datetime.now(UTC)).astimezone(PACIFIC)
    midnight = datetime.combine(at.date() + timedelta(days=1), datetime.min.time(), tzinfo=PACIFIC)
    return midnight.astimezone(UTC)


def parse_limits(tier: str, overrides: str | None) -> dict[str, Limit]:
    """QUOTA_TIER=free uses FREE_TIER; paid counts but never refuses. QUOTA_LIMITS (JSON)
    overrides single models, e.g. {"gemini-3.8-flash": {"rpm": 10, "rpd": 250}}."""
    limits = dict(FREE_TIER) if tier == "free" else {m: Limit() for m in FREE_TIER}
    if overrides:
        data = json.loads(overrides)
        for model, values in data.items():
            limits[model] = Limit(rpm=values.get("rpm"), tpm=values.get("tpm"), rpd=values.get("rpd"))
    return limits


@dataclass
class Usage:
    requests: int = 0  # requests sent today (what Google counts against RPD)
    ok: int = 0
    rejected: int = 0  # Google answered 429
    failed: int = 0  # other errors
    tokens_in: int = 0
    tokens_out: int = 0
    window: deque = field(default_factory=deque)  # (time, input tokens) in the last minute
    cooldown_until: float = 0.0
    cooldown_reason: str = ""
    exhausted: bool = False  # Google said the daily allowance is gone


class QuotaLedger:
    """Counts requests per model and hands out slots within the configured limits."""

    def __init__(
        self,
        limits: dict[str, Limit],
        *,
        reserve: float = 0.0,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.limits = limits
        self.reserve = reserve  # keep this share of each daily allowance unused (a safety margin)
        self.clock = clock
        self.sleep = sleep
        self.day = pacific_day(datetime.fromtimestamp(clock(), UTC))
        self.usage: dict[str, Usage] = {}
        self.cached_hits = 0
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ helpers
    def limit(self, model: str) -> Limit:
        return self.limits.get(model, Limit())

    def _usage(self, model: str) -> Usage:
        today = pacific_day(datetime.fromtimestamp(self.clock(), UTC))
        if today != self.day:  # a new quota day: daily counts start again
            self.day = today
            self.usage = {}
            self.cached_hits = 0
        return self.usage.setdefault(model, Usage())

    def daily_cap(self, model: str) -> int | None:
        rpd = self.limit(model).rpd
        if rpd is None:
            return None
        return max(1, int(rpd * (1 - self.reserve)))

    def check(self, model: str, est_tokens: int = 0) -> tuple[bool, float, str]:
        """(can_send_now, seconds_to_wait, reason). wait = -1 means not today."""
        u = self._usage(model)
        lim = self.limit(model)
        now = self.clock()
        if u.exhausted:
            return False, -1, "daily allowance used up"
        cap = self.daily_cap(model)
        if cap is not None and u.requests >= cap:
            return False, -1, "daily allowance used up"
        if u.cooldown_until > now:
            return False, u.cooldown_until - now, u.cooldown_reason or "Google asked us to slow down"
        while u.window and now - u.window[0][0] >= 60:
            u.window.popleft()
        if lim.rpm is not None and len(u.window) >= lim.rpm:
            return False, 60 - (now - u.window[0][0]) + 0.05, "requests-per-minute limit"
        if lim.tpm is not None and u.window:
            used = sum(t for _, t in u.window)
            if used + est_tokens > lim.tpm:
                return False, 60 - (now - u.window[0][0]) + 0.05, "tokens-per-minute limit"
        return True, 0.0, ""

    async def acquire(self, model: str, est_tokens: int = 0, max_wait: float = 20.0) -> tuple[bool, str]:
        """Reserve one request slot, waiting up to max_wait seconds for a per-minute window.
        Returns (True, "") or (False, reason)."""
        waited = 0.0
        while True:
            async with self._lock:
                ok, wait, reason = self.check(model, est_tokens)
                if ok:
                    u = self._usage(model)
                    u.window.append((self.clock(), est_tokens))
                    u.requests += 1
                    return True, ""
            if wait < 0 or waited + wait > max_wait:
                return False, reason
            await self.sleep(wait)
            waited += wait

    # ------------------------------------------------------------------ outcomes
    def record_ok(self, model: str, tokens_in: int = 0, tokens_out: int = 0) -> None:
        u = self._usage(model)
        u.ok += 1
        u.tokens_in += tokens_in
        u.tokens_out += tokens_out

    def record_rejected(self, model: str, retry_after: float | None = None, daily: bool = False) -> None:
        """Google answered 429. A rejected request doesn't use the daily allowance."""
        u = self._usage(model)
        u.rejected += 1
        u.requests = max(0, u.requests - 1)
        if daily:
            u.exhausted = True
        else:
            u.cooldown_until = self.clock() + max(2.0, retry_after or 20.0)
            u.cooldown_reason = "Google asked us to slow down"

    def record_failed(self, model: str) -> None:
        self._usage(model).failed += 1

    def disable(self, model: str, seconds: float, reason: str) -> None:
        u = self._usage(model)
        u.cooldown_until = self.clock() + seconds
        u.cooldown_reason = reason

    def record_cached(self) -> None:
        self._usage("cache")  # roll the day over if needed
        self.cached_hits += 1

    # ------------------------------------------------------------------ for the interface
    def snapshot(self, models: list[str] | None = None) -> dict:
        now = self.clock()
        names = models or sorted(set(self.limits) | set(self.usage))
        rows = []
        for m in names:
            if m == "cache":
                continue
            u = self._usage(m)
            lim = self.limit(m)
            while u.window and now - u.window[0][0] >= 60:
                u.window.popleft()
            cap = self.daily_cap(m)
            rows.append(
                {
                    "model": m,
                    "label": label(m),
                    "used_today": u.requests,
                    "limit_today": lim.rpd,
                    "usable_today": cap,
                    "left_today": None if cap is None else max(0, cap - u.requests) if not u.exhausted else 0,
                    "used_this_minute": len(u.window),
                    "limit_per_minute": lim.rpm,
                    "ok": u.ok,
                    "rejected": u.rejected,
                    "failed": u.failed,
                    "tokens_in": u.tokens_in,
                    "tokens_out": u.tokens_out,
                    "cooling_down_for": max(0, round(u.cooldown_until - now)) if u.cooldown_until > now else 0,
                    "note": u.cooldown_reason if u.cooldown_until > now else ("used up for today" if u.exhausted else ""),
                }
            )
        return {
            "day": self.day,
            "resets_at": next_reset(datetime.fromtimestamp(now, UTC)).isoformat(),
            "reused_answers": self.cached_hits,
            "models": rows,
        }

    # ------------------------------------------------------------------ persistence
    def dump(self) -> dict:
        return {
            "day": self.day,
            "usage": {
                m: {
                    "requests": u.requests,
                    "ok": u.ok,
                    "rejected": u.rejected,
                    "failed": u.failed,
                    "tokens_in": u.tokens_in,
                    "tokens_out": u.tokens_out,
                    "exhausted": u.exhausted,
                }
                for m, u in self.usage.items()
            },
            "cached_hits": self.cached_hits,
        }

    def load(self, data: dict | None) -> None:
        """Restore today's counts after a restart (counts from another day are ignored)."""
        if not data or data.get("day") != pacific_day(datetime.fromtimestamp(self.clock(), UTC)):
            return
        self.day = data["day"]
        self.cached_hits = int(data.get("cached_hits", 0))
        for m, v in (data.get("usage") or {}).items():
            u = self._usage(m)
            u.requests = max(u.requests, int(v.get("requests", 0)))
            u.ok = max(u.ok, int(v.get("ok", 0)))
            u.rejected = max(u.rejected, int(v.get("rejected", 0)))
            u.failed = max(u.failed, int(v.get("failed", 0)))
            u.tokens_in = max(u.tokens_in, int(v.get("tokens_in", 0)))
            u.tokens_out = max(u.tokens_out, int(v.get("tokens_out", 0)))
            u.exhausted = u.exhausted or bool(v.get("exhausted"))
