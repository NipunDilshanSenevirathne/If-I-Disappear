"""Handover links: created by the person leaving, opened by the person staying."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..ai.live import coach_instruction, create_token
from ..ai.router import ai_scope
from ..auth import User, current_user, limit, limit_ip
from ..config import get_settings
from ..services import households as hs
from ..services import shares
from ..services.evidence import record_attempt
from ..services.views import household_view
from ..store import Store, get_store
from ..workflows.practice import GradeContext, grade_attempt

router = APIRouter(prefix="/api", tags=["handover links"])


class ShareIn(BaseModel):
    person: str
    responsibilities: list[str] = Field(min_length=1, max_length=20)


@router.get("/households/{household_id}/shares")
async def list_shares(household_id: str, user: User = Depends(current_user), store: Store = Depends(get_store)):
    rec = await hs.get_record(store, household_id, user.uid)
    return shares.listing(rec, hs.household_of(rec))


@router.post("/households/{household_id}/shares")
async def create_share(household_id: str, body: ShareIn, user: User = Depends(current_user), store: Store = Depends(get_store)):
    """Create a link. The token is in this response only; it isn't stored."""
    limit(user, "share", 20)
    rec = await hs.get_record(store, household_id, user.uid)
    if rec.owner != user.uid:
        raise HTTPException(403, "Only the person who created this household can share it.")
    async with hs.lock(rec.id):
        rec = await store.get(household_id)
        h = hs.household_of(rec)
        try:
            link, token = shares.create(rec, h, body.person, body.responsibilities, user.uid)
        except shares.ShareError as exc:
            raise HTTPException(400, str(exc)) from exc
        rec = await hs.save(
            store, rec, h, user.uid, "share.create", share=link.id, person=link.person, responsibilities=len(link.responsibilities)
        )
    return {"id": link.id, "token": token, "path": f"/handover#{token}", "shares": shares.listing(rec, h), "household": household_view(rec)}


@router.delete("/households/{household_id}/shares/{share_id}")
async def revoke_share(household_id: str, share_id: str, user: User = Depends(current_user), store: Store = Depends(get_store)):
    rec = await hs.get_record(store, household_id, user.uid)
    async with hs.lock(rec.id):
        rec = await store.get(household_id)
        h = hs.household_of(rec)
        try:
            shares.revoke(rec, share_id)
        except shares.ShareError as exc:
            raise HTTPException(404, str(exc)) from exc
        rec = await hs.save(store, rec, h, user.uid, "share.revoke", share=share_id)
    return shares.listing(rec, h)


# ---------------------------------------------------------------------- the person staying
# The token travels in the request body, never in a URL, so it doesn't end up in
# server logs or browser history. The web page reads it from the link's #fragment.


class TokenIn(BaseModel):
    token: str = Field(min_length=20, max_length=64)


async def _open(store: Store, token: str):
    if not 20 <= len(token) <= 64:
        raise HTTPException(404, "This link isn't valid. Ask for a new one.")
    rec = await store.find_by_share(shares.token_hash(token))
    link = shares.find(rec, token) if rec else None
    if rec is None or link is None:
        raise HTTPException(404, "This link isn't valid any more. Ask for a new one.")
    return rec, link


@router.post("/handover/open")
async def open_handover(body: TokenIn, request: Request, store: Store = Depends(get_store)):
    limit_ip(request, "handover", 60)
    rec, link = await _open(store, body.token)
    h = hs.household_of(rec)
    view = await shares.view(rec, h, link)
    async with hs.lock(rec.id):
        fresh = await store.get(rec.id)
        if fresh is not None:
            for s in fresh.shares:
                if s.id == link.id:
                    s.opened += 1
            await store.put(fresh)
    view["live_voice"] = get_settings().live
    return view


class HandoverAttempt(BaseModel):
    token: str = Field(min_length=20, max_length=64)
    responsibility: str
    transcript: str = Field(min_length=1, max_length=8000)
    coach_transcript: str | None = Field(None, max_length=12000)
    hints_given: int = Field(0, ge=0, le=20)


@router.post("/handover/practice")
async def handover_practice(body: HandoverAttempt, request: Request, store: Store = Depends(get_store)):
    """The person staying practises on their own phone. Same grader, same rules."""
    limit_ip(request, "handover-practice", 20)
    responsibility = body.responsibility
    rec, link = await _open(store, body.token)
    if responsibility not in link.responsibilities:
        raise HTTPException(403, "This link doesn't cover that.")
    h = hs.household_of(rec)
    proc = next((p for p in h.procedures if p.responsibility == responsibility and p.approved), None)
    if proc is None:
        raise HTTPException(404, "The steps for this haven't been approved yet.")
    ents = h.entity_map()
    ctx = GradeContext(proc, link.person, ents[link.person].name, body.transcript, body.coach_transcript, body.hints_given)
    trace: list[dict] = []
    with ai_scope(f"link:{link.id}"):
        attempt = await grade_attempt(ctx, trace)
    async with hs.lock(rec.id):
        rec = await store.get(rec.id)
        h = hs.household_of(rec)
        record_attempt(h, attempt)
        analysis = hs.quick_analysis(h, rec.analysis)
        rec = await hs.save(
            store,
            rec,
            h,
            f"link:{link.id}",
            "practice.attempt",
            responsibility=responsibility,
            person=link.person,
            result=attempt.result,
            analysis=analysis,
            via="handover link",
        )
    steps = {s.id: s for s in proc.steps}
    return {
        "attempt": attempt.model_dump(mode="json"),
        "missed_steps": [
            {"id": sid, "text": steps[sid].text, "critical": steps[sid].critical, "hint": steps[sid].hint}
            for sid in attempt.missed
            if sid in steps
        ],
        "trace": trace,
    }


class VoiceIn(BaseModel):
    token: str = Field(min_length=20, max_length=64)
    responsibility: str


@router.post("/handover/voice")
async def handover_voice(body: VoiceIn, request: Request, store: Store = Depends(get_store)):
    """A single-use Gemini Live token, so the person staying can practise by talking."""
    limit_ip(request, "handover-live", 6)
    if not get_settings().live:
        raise HTTPException(503, "Spoken practice needs live mode. You can practise by typing instead.")
    responsibility = body.responsibility
    rec, link = await _open(store, body.token)
    if responsibility not in link.responsibilities:
        raise HTTPException(403, "This link doesn't cover that.")
    h = hs.household_of(rec)
    proc = next((p for p in h.procedures if p.responsibility == responsibility and p.approved), None)
    if proc is None:
        raise HTTPException(404, "The steps for this haven't been approved yet.")
    ents = h.entity_map()
    label = ents[responsibility].name
    instruction = coach_instruction(
        proc,
        ents[link.person].name,
        ents[h.settings.leaver].name if h.settings.leaver in ents else "the person leaving",
        label[:1].lower() + label[1:],
        proc.scenario_prompt,
    )
    try:
        return create_token(instruction)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, "Couldn't start spoken practice right now. You can practise by typing instead.") from exc
