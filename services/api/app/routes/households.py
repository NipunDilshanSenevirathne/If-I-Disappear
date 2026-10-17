"""Households, the demo, people and settings."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import User, current_user, limit
from ..config import get_settings
from ..domain.claims import Entity
from ..domain.household import household_to_dict
from ..services import households as hs
from ..services.views import household_view
from ..store import Store, get_store

router = APIRouter(prefix="/api", tags=["households"])


class DemoRequest(BaseModel):
    reset: bool = False
    household: str | None = Field(None, max_length=40, description="Which sample household (default: the main demo)")


class StageRequest(BaseModel):
    stage: str = Field(pattern="^(capture|after_handover)$")


class VariantRequest(BaseModel):
    variant: str | None = None


class PersonIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    role: str = Field("household", pattern="^(backup|household|helper)$")
    minor: bool = False


class NewHousehold(BaseModel):
    name: str = Field("Our household", max_length=80)
    leaver_name: str = Field(min_length=1, max_length=60)
    departure: date
    horizon_days: int = Field(90, ge=7, le=365)
    destination: str | None = Field(None, max_length=60)
    absence: str = Field("travel", pattern="^(travel|hospital|other)$")
    people: list[PersonIn] = Field(default_factory=list, max_length=12)


class SettingsPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    departure: date | None = None
    horizon_days: int | None = Field(None, ge=7, le=365)
    budget_minutes: int | None = Field(None, ge=10, le=600)
    destination: str | None = Field(None, max_length=60)
    absence: str | None = Field(None, pattern="^(travel|hospital|other)$")


@router.get("/demos")
async def list_demos():
    """The sample households anyone can open (all synthetic), with the engine's summary of each."""
    return hs.demo_cards()


@router.post("/demo")
async def start_demo(body: DemoRequest, user: User = Depends(current_user), store: Store = Depends(get_store)):
    """Your own copy of a sample household (each visitor gets an isolated copy)."""
    limit(user, "demo", 20)
    source = body.household or get_settings().demo_household
    if source not in hs.demo_sources():
        raise HTTPException(404, "There's no sample household with that name.")
    rec = await store.find_demo(user.uid, source)
    if rec is None:
        rec = await hs.create_demo(store, user.uid, source=source)
    elif body.reset:
        async with hs.lock(rec.id):
            rec = await hs.create_demo(store, user.uid, source=source, existing=rec)
    return household_view(rec)


@router.post("/demo/{household_id}/stage")
async def demo_stage(household_id: str, body: StageRequest, user: User = Depends(current_user), store: Store = Depends(get_store)):
    rec = await hs.get_record(store, household_id, user.uid)
    if not rec.demo:
        raise HTTPException(400, "Only the demo household can jump in time.")
    if body.stage not in hs.stages_for(rec):
        raise HTTPException(400, "This sample household has no later stage.")
    async with hs.lock(rec.id):
        variant = hs.household_of(rec).variant
        rec = await hs.create_demo(store, user.uid, stage=body.stage, variant=variant, existing=rec)
    return household_view(rec)


@router.post("/demo/{household_id}/variant")
async def demo_variant(household_id: str, body: VariantRequest, user: User = Depends(current_user), store: Store = Depends(get_store)):
    rec = await hs.get_record(store, household_id, user.uid)
    if not rec.demo:
        raise HTTPException(400, "Variants are only for the demo household.")
    known = {v["id"] for v in hs.variants_for(rec)}
    if body.variant is not None and body.variant not in known:
        raise HTTPException(400, "Unknown variant.")
    async with hs.lock(rec.id):
        h = hs.household_of(rec)
        stage = "after_handover" if h.stages_applied else "capture"
        rec = await hs.create_demo(store, user.uid, stage=stage, variant=body.variant, existing=rec)
    return household_view(rec)


@router.get("/households")
async def my_households(user: User = Depends(current_user), store: Store = Depends(get_store)):
    recs = await store.list_for(user.uid)
    return [
        {
            "id": r.id,
            "name": r.data.get("settings", {}).get("name"),
            "demo": r.demo,
            "updated": r.updated.isoformat(),
            "summary": ((r.analysis or {}).get("result") or {}).get("summary"),
        }
        for r in sorted(recs, key=lambda r: r.updated, reverse=True)
    ]


@router.post("/households")
async def create_household(body: NewHousehold, user: User = Depends(current_user), store: Store = Depends(get_store)):
    limit(user, "create", 10)
    rec = await hs.create_household(
        store,
        user.uid,
        body.name,
        body.leaver_name,
        body.departure,
        [p.model_dump() for p in body.people],
        body.horizon_days,
        destination=(body.destination or "").strip() or None,
        absence=body.absence,
    )
    return household_view(rec)


@router.get("/households/{household_id}")
async def get_household(household_id: str, user: User = Depends(current_user), store: Store = Depends(get_store)):
    return household_view(await hs.get_record(store, household_id, user.uid))


@router.get("/households/{household_id}/pulse")
async def pulse(household_id: str, user: User = Depends(current_user), store: Store = Depends(get_store)):
    """A tiny 'has anything changed?' answer for the live dashboard (polled every few seconds)."""
    rec = await hs.get_record(store, household_id, user.uid)
    summary = ((rec.analysis or {}).get("result") or {}).get("summary")
    return {"rev": rec.rev, "updated": rec.updated.isoformat(), "summary": summary, "history": len(rec.history)}


@router.patch("/households/{household_id}/settings")
async def patch_settings(household_id: str, body: SettingsPatch, user: User = Depends(current_user), store: Store = Depends(get_store)):
    rec = await hs.get_record(store, household_id, user.uid)
    async with hs.lock(rec.id):
        rec = await store.get(household_id)
        h = hs.household_of(rec)
        changes = {k: v for k, v in body.model_dump().items() if v is not None}
        if "destination" in changes:
            changes["destination"] = changes["destination"].strip() or None  # an empty box clears it
        if "name" in changes:
            changes["name"] = changes["name"].strip() or h.settings.name
        h.settings = h.settings.model_copy(update=changes)
        h.version += 1
        analysis = hs.quick_analysis(h, rec.analysis)
        rec = await hs.save(store, rec, h, user.uid, "settings.update", analysis=analysis, fields=sorted(changes))
    return household_view(rec)


@router.post("/households/{household_id}/people")
async def add_person(household_id: str, body: PersonIn, user: User = Depends(current_user), store: Store = Depends(get_store)):
    rec = await hs.get_record(store, household_id, user.uid)
    async with hs.lock(rec.id):
        rec = await store.get(household_id)
        h = hs.household_of(rec)
        base = "".join(ch for ch in body.name.lower() if ch.isalnum()) or "person"
        ids = {e.id for e in h.entities}
        pid, n = base, 2
        while pid in ids:
            pid, n = f"{base}{n}", n + 1
        h.entities.append(Entity(id=pid, kind="person", name=body.name.strip(), role=body.role, minor=body.minor))
        h.version += 1
        rec = await hs.save(store, rec, h, user.uid, "person.add", person=pid)
    return household_view(rec)


@router.delete("/households/{household_id}")
async def delete_household(household_id: str, user: User = Depends(current_user), store: Store = Depends(get_store)):
    from ..store import get_blobs

    rec = await hs.get_record(store, household_id, user.uid)
    if rec.owner != user.uid:
        raise HTTPException(403, "Only the person who created this household can delete it.")
    await store.delete(household_id)
    await get_blobs().delete_prefix(f"households/{household_id}")
    return {"deleted": household_id}


@router.get("/households/{household_id}/export")
async def export_household(household_id: str, user: User = Depends(current_user), store: Store = Depends(get_store)):
    """Everything we hold about this household, as JSON (data portability)."""
    rec = await hs.get_record(store, household_id, user.uid)
    h = hs.household_of(rec)
    return {"household": household_to_dict(h), "analysis": rec.analysis, "log": [e.model_dump(mode="json") for e in rec.log]}
