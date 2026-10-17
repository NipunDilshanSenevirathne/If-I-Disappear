"""Loading, saving, creating and analysing household records."""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from datetime import date, timedelta
from functools import lru_cache

from fastapi import HTTPException

from ..config import get_settings
from ..domain.claims import Entity, HouseholdSettings
from ..domain.household import (
    Household,
    apply_variant,
    demo_household,
    demo_index,
    household_from_dict,
    household_to_dict,
    load_stage,
    load_variants,
)
from ..store import HouseholdRecord, Store
from ..workflows.analysis import AnalysisContext, analyse, run_state_machine

_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


def lock(household_id: str) -> asyncio.Lock:
    """One writer per household per instance (the store also checks revisions)."""
    return _locks[household_id]


def household_of(rec: HouseholdRecord) -> Household:
    return household_from_dict(rec.data)


async def get_record(store: Store, household_id: str, uid: str) -> HouseholdRecord:
    rec = await store.get(household_id)
    if rec is None:
        raise HTTPException(404, "This household doesn't exist or was deleted.")
    if not rec.can_read(uid):
        raise HTTPException(403, "You don't have access to this household.")
    return rec


async def save(
    store: Store, rec: HouseholdRecord, h: Household, actor: str, action: str, *, analysis: dict | None = None, **detail
) -> HouseholdRecord:
    rec.data = household_to_dict(h)
    if analysis is not None:
        rec.analysis = analysis
        summary = (analysis.get("result") or {}).get("summary")
        if summary:
            rec.add_history(action, summary)
    rec.add_log(actor, action, **detail)
    return await store.put(rec)


# ---------------------------------------------------------------------- analysis


async def full_analysis(h: Household) -> dict:
    """Engine plus the AI review (challenger). Runs as a background job."""
    return await analyse(AnalysisContext(h))


def quick_analysis(h: Household, previous: dict | None) -> dict:
    """Engine only (fast and deterministic). Keeps the AI review of findings that
    still exist unchanged, so recording evidence doesn't wait on a model."""
    ctx = AnalysisContext(h)
    trace: list[dict] = []
    run_state_machine(ctx, trace, "Updated by the engine after a change. Run 'Check again' for a fresh AI review.")
    snap = ctx.snapshot(trace, "engine-refresh")
    old = {f["id"]: f for f in (previous or {}).get("findings", [])}
    for f in snap["findings"]:
        prev = old.get(f["id"])
        if prev and prev.get("challenge") and prev.get("summary") == f["summary"]:
            f["challenge"] = prev["challenge"]
            f["status"] = prev.get("status", f["status"])
    if previous:
        snap["challenge"] = previous.get("challenge", "none")
        # keep the steps of the last full check (with its models), not those of an engine refresh
        refreshed = previous.get("workflow") == "engine-refresh"
        snap["review_trace"] = (previous.get("review_trace") or []) if refreshed else previous.get("trace", [])
        snap["review_at"] = previous.get("review_at") if refreshed else previous.get("computed_at")
    return snap


# ---------------------------------------------------------------------- creating households


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def demo_sources() -> list[str]:
    return [d["id"] for d in demo_index()]


@lru_cache
def demo_cards() -> list[dict]:
    """The sample households for the picker and the landing page, with what the engine
    concludes about each (computed once, by the same code the app uses)."""
    out = []
    for item in demo_index():
        card = {k: v for k, v in item.items() if k != "languages"}
        try:
            h = demo_household(item["id"], "capture", None)
            snap = quick_analysis(h, None)
            s = snap["result"]["summary"]
            results = snap["result"]["responsibilities"]
            stops = sorted(
                (r for r in results if r.get("first_problem") and r["state"] == "blocked"),
                key=lambda r: (r["first_problem"], -r["weight"], r["label"]),
            )
            card.update(
                summary={k: s[k] for k in ("ready", "total", "blocked", "needs_confirmation", "needs_handover")},
                plan_minutes=snap["plan"]["minutes"],
                plan_after=snap["plan"]["after"]["ready"],
                plan_steps=len(snap["plan"]["steps"]),
                first_problem=min((r["first_problem"] for r in results if r.get("first_problem")), default=None),
                stops=[{"label": r["label"], "date": r["first_problem"]} for r in stops[:4]],
                findings=len(snap["findings"]),
            )
        except Exception:  # noqa: BLE001 - the picker still works without the numbers
            card.update(summary=None, plan_minutes=None, plan_after=None, plan_steps=None, first_problem=None, stops=[], findings=None)
        out.append(card)
    return out


def stages_for(rec: HouseholdRecord) -> list[str]:
    if not rec.demo:
        return []
    return ["capture"] + (["after_handover"] if load_stage(rec.demo_source or "perera") is not None else [])


async def create_demo(
    store: Store,
    uid: str,
    *,
    source: str | None = None,
    stage: str = "capture",
    variant: str | None = None,
    existing: HouseholdRecord | None = None,
) -> HouseholdRecord:
    fixture_id = source or (existing.demo_source if existing else None) or get_settings().demo_household
    h = demo_household(fixture_id, stage, variant)
    rec = existing or HouseholdRecord(id=_new_id("demo"), owner=uid, demo=True, demo_source=fixture_id, data={})
    rec.data = household_to_dict(h)
    rec.analysis = quick_analysis(h, None)
    summary = rec.analysis["result"]["summary"]
    if stage == "capture" and variant is None:
        rec.history = []
        rec.add_history("demo.loaded", summary)
    elif stage == "after_handover":
        rec.add_history("demo.week_later", summary)
    else:
        rec.add_history(f"demo.variant:{variant}", summary)
    rec.add_log(uid, "demo.reset" if existing else "demo.create", stage=stage, variant=variant)
    return await store.put(rec)


def variants_for(rec: HouseholdRecord) -> list[dict]:
    if not rec.demo:
        return []
    return [{"id": v.id, "title": v.title, "summary": v.summary} for v in load_variants(rec.demo_source or "perera")]


async def create_household(
    store: Store,
    uid: str,
    name: str,
    leaver_name: str,
    departure: date,
    people: list[dict],
    horizon_days: int = 90,
    *,
    destination: str | None = None,
    absence: str = "travel",
) -> HouseholdRecord:
    hid = _new_id("hh")
    entities = [Entity(id="leaver", kind="person", name=leaver_name.strip() or "Me", role="leaver")]
    used = {"leaver"}
    for p in people:
        base = "".join(ch for ch in p.get("name", "").lower() if ch.isalnum()) or "person"
        pid, n = base, 2
        while pid in used:
            pid, n = f"{base}{n}", n + 1
        used.add(pid)
        entities.append(Entity(id=pid, kind="person", name=p["name"].strip(), role=p.get("role", "household"), minor=bool(p.get("minor"))))
    settings = HouseholdSettings(
        id=hid,
        name=name.strip() or "Our household",
        leaver="leaver",
        departure=departure,
        horizon_days=horizon_days,
        destination=destination,
        absence=absence,
        airport_from="HOME",
        assessment_date=date.today(),
        synthetic=False,
        budget_minutes=60,
    )
    h = Household(settings=settings, entities=entities, sources=[], claims=[])
    rec = HouseholdRecord(id=hid, owner=uid, data=household_to_dict(h))
    rec.analysis = quick_analysis(h, None)
    rec.add_history("household.create", rec.analysis["result"]["summary"])
    rec.add_log(uid, "household.create")
    return await store.put(rec)


__all__ = [
    "apply_variant",
    "create_demo",
    "demo_cards",
    "create_household",
    "demo_index",
    "demo_sources",
    "full_analysis",
    "get_record",
    "household_of",
    "lock",
    "quick_analysis",
    "save",
    "stages_for",
    "timedelta",
    "variants_for",
]
