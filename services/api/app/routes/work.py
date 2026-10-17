"""Analysis, plan, findings, evidence, practice, the Continuity Card and jobs."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from ..ai.live import coach_instruction, create_token
from ..ai.router import ai_scope
from ..auth import User, current_user, limit
from ..config import get_settings
from ..domain.household import Household
from ..engine.evaluate import evaluate
from ..engine.repair import plan
from ..engine.serialize import plan_dict
from ..services import households as hs
from ..services import jobs, procedures
from ..services.card import build_card
from ..services.evidence import EvidenceError, EvidenceInput, answer_finding, record_attempt, record_step_evidence
from ..services.explore import ExploreError, explore, options
from ..services.manual import ManualError, ResponsibilityIn, add_responsibility
from ..services.views import household_view
from ..store import Store, get_blobs, get_store
from ..workflows.practice import GradeContext, grade_attempt

router = APIRouter(prefix="/api", tags=["work"])


# ---------------------------------------------------------------------- analysis


class AnalyzeRequest(BaseModel):
    language: str | None = None  # older clients; everything is in English


@router.post("/households/{household_id}/analyze")
async def analyze(
    household_id: str, body: AnalyzeRequest | None = None, user: User = Depends(current_user), store: Store = Depends(get_store)
):
    """Full analysis with the AI review, as a job (poll /api/jobs/{id})."""
    limit(user, "analyze", 12)
    await hs.get_record(store, household_id, user.uid)

    async def work(job):
        async with hs.lock(household_id):
            rec = await store.get(household_id)
            h = hs.household_of(rec)
            with ai_scope(user.uid):
                snap = await hs.full_analysis(h)
            job.progress.extend(snap["trace"])
            await hs.save(store, rec, h, user.uid, "analysis.run", analysis=snap, workflow=snap["workflow"])
            return {
                "summary": snap["result"]["summary"],
                "findings": len(snap["findings"]),
                "workflow": snap["workflow"],
                "challenge": snap["challenge"],
            }

    job = await jobs.start(store, kind="analyze", household_id=household_id, owner=user.uid, work=work)
    return {"job": job.model_dump(mode="json")}


class PlanRequest(BaseModel):
    budget_minutes: int = Field(60, ge=10, le=600)


@router.post("/households/{household_id}/plan")
async def replan(household_id: str, body: PlanRequest, user: User = Depends(current_user), store: Store = Depends(get_store)):
    """Recompute the plan for another time budget (engine only, instant)."""
    rec = await hs.get_record(store, household_id, user.uid)
    h = hs.household_of(rec)
    c = h.compile()
    p = plan(c.world, c.scenario, evaluate(c.world, c.scenario), budget_minutes=body.budget_minutes)
    return plan_dict(c.world, c.scenario, p)


# ---------------------------------------------------------------------- explore (what if)


class ExploreIn(BaseModel):
    also_away: list[str] = Field(default_factory=list, max_length=10)
    unavailable: list[str] = Field(default_factory=list, max_length=20)
    keep_using: list[str] = Field(default_factory=list, max_length=20)
    departure: date | None = None
    days: int | None = Field(None, ge=1, le=365)


@router.get("/households/{household_id}/explore")
async def explore_options(household_id: str, user: User = Depends(current_user), store: Store = Depends(get_store)):
    """What can be switched on the Explore screen."""
    rec = await hs.get_record(store, household_id, user.uid)
    return options(hs.household_of(rec))


@router.post("/households/{household_id}/explore")
async def explore_scenario(household_id: str, body: ExploreIn, user: User = Depends(current_user), store: Store = Depends(get_store)):
    """Evaluate a changed copy of the absence. Nothing is saved; no model is used."""
    limit(user, "explore", 120)
    rec = await hs.get_record(store, household_id, user.uid)
    try:
        return explore(hs.household_of(rec), **body.model_dump())
    except ExploreError as exc:
        raise HTTPException(400, str(exc)) from exc


# ---------------------------------------------------------------------- adding by hand


@router.post("/households/{household_id}/responsibilities")
async def add_by_hand(household_id: str, body: ResponsibilityIn, user: User = Depends(current_user), store: Store = Depends(get_store)):
    """Add a responsibility from a short form. No AI; the facts are saved as reviewed."""
    limit(user, "manual", 30)
    rec = await hs.get_record(store, household_id, user.uid)
    async with hs.lock(rec.id):
        rec = await store.get(household_id)
        h = hs.household_of(rec)
        if sum(1 for e in h.entities if e.kind == "responsibility") >= 20:
            raise HTTPException(400, "A household can track up to 20 responsibilities.")
        try:
            added = add_responsibility(h, body, user.uid)
        except ManualError as exc:
            raise HTTPException(400, str(exc)) from exc
        analysis = hs.quick_analysis(h, rec.analysis)
        rec = await hs.save(store, rec, h, user.uid, "responsibility.add", analysis=analysis, responsibility=added["responsibility"])
    return {"added": added, "household": household_view(rec)}


class ScopeIn(BaseModel):
    responsibility: str
    include: bool


@router.post("/households/{household_id}/scope")
async def set_scope(household_id: str, body: ScopeIn, user: User = Depends(current_user), store: Store = Depends(get_store)):
    """Leave a responsibility out of this plan (or bring it back). The count says so."""
    rec = await hs.get_record(store, household_id, user.uid)
    async with hs.lock(rec.id):
        rec = await store.get(household_id)
        h = hs.household_of(rec)
        ids = [e.id for e in h.entities if e.kind == "responsibility"]
        if body.responsibility not in ids:
            raise HTTPException(404, "No such responsibility.")
        scope = set(h.settings.in_scope if h.settings.in_scope is not None else ids)
        if body.include:
            scope.add(body.responsibility)
        else:
            scope.discard(body.responsibility)
        h.settings = h.settings.model_copy(update={"in_scope": None if scope >= set(ids) else sorted(scope)})
        h.version += 1
        analysis = hs.quick_analysis(h, rec.analysis)
        rec = await hs.save(
            store, rec, h, user.uid, "scope.change", analysis=analysis, responsibility=body.responsibility, include=body.include
        )
    return household_view(rec)


# ---------------------------------------------------------------------- findings


class Answer(BaseModel):
    keep_claim: str | None = None
    person: str | None = None
    responsibility: str | None = None
    value: str | None = None
    confirm: bool | None = None


@router.post("/households/{household_id}/findings/{finding_id:path}/answer")
async def answer(household_id: str, finding_id: str, body: Answer, user: User = Depends(current_user), store: Store = Depends(get_store)):
    rec = await hs.get_record(store, household_id, user.uid)
    async with hs.lock(rec.id):
        rec = await store.get(household_id)
        h = hs.household_of(rec)
        finding = next((f for f in (rec.analysis or {}).get("findings", []) if f["id"] == finding_id), None)
        if finding is None:
            raise HTTPException(404, "That finding has changed. Refresh and try again.")
        try:
            changes = answer_finding(h, finding, body.model_dump(), user.uid)
        except EvidenceError as exc:
            raise HTTPException(400, str(exc)) from exc
        analysis = hs.quick_analysis(h, rec.analysis)
        rec = await hs.save(store, rec, h, user.uid, "finding.answer", finding=finding_id, changes=changes, analysis=analysis)
    return {"changes": changes, "household": household_view(rec)}


# ---------------------------------------------------------------------- evidence


@router.post("/households/{household_id}/evidence")
async def evidence(
    household_id: str,
    step_id: str = Form(...),
    kind: str = Form(...),
    note: str | None = Form(None, max_length=500),
    witness: str | None = Form(None),
    new_date: date | None = Form(None),
    on: date | None = Form(None),
    file: UploadFile | None = File(None),
    user: User = Depends(current_user),
    store: Store = Depends(get_store),
):
    """Record evidence for a plan step. This, not the plan, changes the result."""
    limit(user, "evidence", 60)
    rec = await hs.get_record(store, household_id, user.uid)
    async with hs.lock(rec.id):
        rec = await store.get(household_id)
        h = hs.household_of(rec)
        key = mime = None
        if file is not None:
            data = await file.read()
            if len(data) > get_settings().max_upload_mb * 1024 * 1024:
                raise HTTPException(413, "That file is too large.")
            mime = (file.content_type or "application/octet-stream").split(";")[0]
            key = await get_blobs().put(
                f"households/{household_id}/evidence/{step_id.replace(':', '_')}-{file.filename or 'file'}", data, mime
            )
        try:
            out = record_step_evidence(
                h,
                EvidenceInput(
                    step_id=step_id, kind=kind, note=note, witness=witness, new_date=new_date, file_key=key, mime_type=mime, on=on
                ),
                user.uid,
            )
        except EvidenceError as exc:
            raise HTTPException(400, str(exc)) from exc
        analysis = hs.quick_analysis(h, rec.analysis)
        rec = await hs.save(store, rec, h, user.uid, "evidence.record", step=step_id, kind=kind, changes=out["changes"], analysis=analysis)
    return {"recorded": out, "household": household_view(rec)}


# ---------------------------------------------------------------------- approved steps


class StepIn(BaseModel):
    text: str = Field(max_length=300)
    critical: bool = False
    hint: str | None = Field(None, max_length=200)


class StepsIn(BaseModel):
    steps: list[StepIn] = Field(min_length=1, max_length=procedures.MAX_STEPS)
    scenario_prompt: str | None = Field(None, max_length=300)


@router.get("/households/{household_id}/procedures/{responsibility}")
async def procedure_draft(household_id: str, responsibility: str, user: User = Depends(current_user), store: Store = Depends(get_store)):
    """The approved steps if there are some, otherwise a draft written by code from the household's own facts."""
    rec = await hs.get_record(store, household_id, user.uid)
    try:
        return procedures.draft(hs.household_of(rec), responsibility)
    except procedures.StepError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.put("/households/{household_id}/procedures/{responsibility}")
async def procedure_save(
    household_id: str, responsibility: str, body: StepsIn, user: User = Depends(current_user), store: Store = Depends(get_store)
):
    """Approve the steps for a task (a new version each time). Practice is checked against these."""
    rec = await hs.get_record(store, household_id, user.uid)
    async with hs.lock(household_id):
        rec = await store.get(household_id)
        h = hs.household_of(rec)
        try:
            proc = procedures.save(h, responsibility, [s.model_dump() for s in body.steps], body.scenario_prompt)
        except procedures.StepError as exc:
            raise HTTPException(400, str(exc)) from exc
        rec = await hs.save(
            store, rec, h, user.uid, "procedure.approve", responsibility=responsibility, version=proc.version, steps=len(proc.steps)
        )
    return household_view(rec)


# ---------------------------------------------------------------------- practice


def _procedure(h: Household, responsibility: str):
    proc = next((p for p in h.procedures if p.responsibility == responsibility), None)
    if proc is None:
        raise HTTPException(404, "There are no approved steps for this yet. Add them before practising.")
    return proc


@router.get("/households/{household_id}/practice/{responsibility}")
async def practice_brief(
    household_id: str,
    responsibility: str,
    person: str = Query(...),
    user: User = Depends(current_user),
    store: Store = Depends(get_store),
):
    rec = await hs.get_record(store, household_id, user.uid)
    h = hs.household_of(rec)
    proc = _procedure(h, responsibility)
    ents = h.entity_map()
    if person not in ents:
        raise HTTPException(404, "Unknown person.")
    attempts = [a.model_dump(mode="json") for a in h.practice_attempts if a.person == person and a.responsibility == responsibility]
    return {
        "responsibility": responsibility,
        "label": ents[responsibility].name,
        "person": person,
        "person_name": ents[person].name,
        "scenario": proc.scenario_prompt,
        "step_count": len(proc.steps),
        "key_steps": sum(1 for s in proc.steps if s.critical),
        "steps": [{"id": s.id, "text": s.text, "critical": s.critical, "hint": s.hint} for s in proc.steps],
        "live_voice": get_settings().live,
        "attempts": attempts,
    }


class TokenRequest(BaseModel):
    person: str


@router.post("/households/{household_id}/practice/{responsibility}/token")
async def practice_token(
    household_id: str, responsibility: str, body: TokenRequest, user: User = Depends(current_user), store: Store = Depends(get_store)
):
    """A single-use Gemini Live token with the practice partner's instructions locked in."""
    limit(user, "live", 6)
    if not get_settings().live:
        raise HTTPException(503, "Spoken practice needs live mode. You can practise by typing instead.")
    rec = await hs.get_record(store, household_id, user.uid)
    h = hs.household_of(rec)
    proc = _procedure(h, responsibility)
    ents = h.entity_map()
    instruction = coach_instruction(
        proc,
        ents[body.person].name if body.person in ents else body.person,
        ents[h.settings.leaver].name if h.settings.leaver in ents else "the person leaving",
        ents[responsibility].name[:1].lower() + ents[responsibility].name[1:],
        proc.scenario_prompt,
    )
    try:
        return create_token(instruction)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, "Couldn't start spoken practice right now. You can practise by typing instead.") from exc


class AttemptIn(BaseModel):
    person: str
    transcript: str = Field(min_length=1, max_length=8000)
    coach_transcript: str | None = Field(None, max_length=12000)
    hints_given: int = Field(0, ge=0, le=20)
    mode: str = Field("text", pattern="^(text|voice)$")


@router.post("/households/{household_id}/practice/{responsibility}/attempts")
async def practice_attempt(
    household_id: str, responsibility: str, body: AttemptIn, user: User = Depends(current_user), store: Store = Depends(get_store)
):
    """Grade a teach-back and record it. The model marks steps; code decides the result."""
    limit(user, "grade", 20)
    rec = await hs.get_record(store, household_id, user.uid)
    h = hs.household_of(rec)
    proc = _procedure(h, responsibility)
    ents = h.entity_map()
    if body.person not in ents or ents[body.person].minor:
        raise HTTPException(400, "Choose an adult in the household.")
    ctx = GradeContext(proc, body.person, ents[body.person].name, body.transcript, body.coach_transcript, body.hints_given)
    trace: list[dict] = []
    with ai_scope(user.uid):
        attempt = await grade_attempt(ctx, trace)
    async with hs.lock(rec.id):
        rec = await store.get(household_id)
        h = hs.household_of(rec)
        event = record_attempt(h, attempt)
        analysis = hs.quick_analysis(h, rec.analysis)
        rec = await hs.save(
            store,
            rec,
            h,
            user.uid,
            "practice.attempt",
            responsibility=responsibility,
            person=body.person,
            result=attempt.result,
            analysis=analysis,
        )
    steps = {s.id: s for s in proc.steps}
    return {
        "attempt": attempt.model_dump(mode="json"),
        "missed_steps": [
            {"id": sid, "text": steps[sid].text, "critical": steps[sid].critical, "hint": steps[sid].hint}
            for sid in attempt.missed
            if sid in steps
        ],
        "event": event.model_dump(mode="json") if event else None,
        "trace": trace,
        "household": household_view(rec),
    }


# ---------------------------------------------------------------------- card and jobs


@router.get("/households/{household_id}/card")
async def card(household_id: str, user: User = Depends(current_user), store: Store = Depends(get_store)):
    rec = await hs.get_record(store, household_id, user.uid)
    return await build_card(hs.household_of(rec))


@router.get("/jobs/{job_id}")
async def job_status(job_id: str, user: User = Depends(current_user), store: Store = Depends(get_store)):
    job = await store.get_job(job_id)
    if job is None or job.owner != user.uid:
        raise HTTPException(404, "No such job.")
    return job.model_dump(mode="json")
