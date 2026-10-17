"""Capturing sources (voice notes, photos, PDFs, typed notes) and reviewing claims."""

from __future__ import annotations

import datetime as dt
import mimetypes
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..ai.router import ai_scope
from ..auth import User, current_user, limit
from ..config import get_settings
from ..domain.claims import ScheduleSpec, Source, WindowSpec
from ..services import households as hs
from ..services import jobs
from ..services.views import household_view
from ..store import Store, get_blobs, get_store
from ..workflows.ingest import IngestContext, ingest_source

router = APIRouter(prefix="/api", tags=["sources"])


@router.get("/samples")
async def sample_files():
    """Sample documents anyone can try (all synthetic, marked SAMPLE): a bill, a clinic book..."""
    from ..domain.household import FIXTURES, load_household

    out = []
    for folder in sorted(p for p in FIXTURES.iterdir() if (p / "files").is_dir()):
        try:
            titles = {src.id: src.title for src in load_household(folder.name).sources}
        except FileNotFoundError:
            continue
        for f in sorted((folder / "files").iterdir()):
            mime = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
            if mime not in ALLOWED or f.stem not in titles:
                continue
            out.append(
                {
                    "household": folder.name,
                    "id": f.stem,
                    "title": titles[f.stem],
                    "kind": ALLOWED[mime],
                    "mime_type": mime,
                    "url": f"/api/samples/{folder.name}/{f.name}",
                }
            )
    return out


@router.get("/samples/{household}/{name}")
async def sample_file(household: str, name: str):
    from ..domain.household import FIXTURES

    if not (household.replace("_", "").isalnum() and name.replace(".", "").replace("_", "").replace("-", "").isalnum()):
        raise HTTPException(404, "No such sample.")
    path = (FIXTURES / household / "files" / name).resolve()
    if FIXTURES.resolve() not in path.parents or not path.is_file():
        raise HTTPException(404, "No such sample.")
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return Response(path.read_bytes(), media_type=mime, headers={"Cache-Control": "public, max-age=86400"})


MAX_SOURCES = 40
ALLOWED = {
    "image/png": "image",
    "image/jpeg": "image",
    "image/webp": "image",
    "image/heic": "image",
    "application/pdf": "pdf",
    "audio/webm": "voice",
    "audio/ogg": "voice",
    "audio/mpeg": "voice",
    "audio/mp4": "voice",
    "audio/x-m4a": "voice",
    "audio/wav": "voice",
    "audio/x-wav": "voice",
}


def _ingest_work(store: Store, household_id: str, source_id: str, uid: str, data: bytes | None, mime: str | None):
    async def work(job):
        async with hs.lock(household_id):
            rec = await store.get(household_id)
            h = hs.household_of(rec)
            source = next(s for s in h.sources if s.id == source_id)
            ctx = IngestContext(h, source, data, mime, fixture_id=rec.demo_source if rec.demo else None)
            try:
                with ai_scope(uid):
                    result = await ingest_source(ctx, job.progress)
            except Exception as exc:
                source.status = "error"
                source.error = str(exc) if str(exc) else "The source couldn't be read."
                await hs.save(store, rec, h, uid, "source.error", source=source_id)
                raise
            h.version += 1
            await hs.save(store, rec, h, uid, "source.extract", source=source_id, added=result["added"], merged=result["merged"])
            return {**result, "trace": job.progress}

    return work


@router.post("/households/{household_id}/sources")
async def add_source(
    household_id: str,
    kind: str = Form("text"),
    title: str = Form("", max_length=120),
    text: str = Form("", max_length=20000),
    speaker: str | None = Form(None),
    consent: bool = Form(False),
    file: UploadFile | None = File(None),
    user: User = Depends(current_user),
    store: Store = Depends(get_store),
):
    """Add a voice note, photo, PDF or typed note. Reading and extraction run as a job."""
    limit(user, "source", 20)
    if get_settings().live and not consent:
        raise HTTPException(400, "Please confirm that this can be sent to Google's Gemini models to be read.")
    rec = await hs.get_record(store, household_id, user.uid)
    data = None
    mime = None
    if file is not None:
        data = await file.read()
        if len(data) > get_settings().max_upload_mb * 1024 * 1024:
            raise HTTPException(413, f"Files can be up to {get_settings().max_upload_mb} MB.")
        mime = (file.content_type or mimetypes.guess_type(file.filename or "")[0] or "").split(";")[0]
        if mime not in ALLOWED:
            raise HTTPException(415, "Use a photo (JPG, PNG), a PDF or a voice recording.")
        kind = ALLOWED[mime]
    elif not text.strip():
        raise HTTPException(400, "Add a file or type a note.")
    else:
        kind = "text"
    async with hs.lock(rec.id):
        rec = await store.get(household_id)
        h = hs.household_of(rec)
        if len(h.sources) >= MAX_SOURCES:
            raise HTTPException(400, f"A household can have up to {MAX_SOURCES} sources. Remove one you no longer need first.")
        sid = f"U{len([s for s in h.sources if s.id.startswith('U')]) + 1:02d}-{uuid.uuid4().hex[:4]}"
        key = None
        if data is not None:
            ext = mimetypes.guess_extension(mime) or ""
            key = await get_blobs().put(f"households/{household_id}/{sid}{ext}", data, mime)
        people = {e.id for e in h.entities if e.kind == "person"}
        source = Source(
            id=sid,
            kind=kind,
            title=title.strip() or {"voice": "Voice note", "image": "Photo", "pdf": "Document", "text": "Note"}[kind],
            text=text,
            speaker=speaker if speaker in people else None,
            file=key,
            mime_type=mime,
            observed=dt.date.today(),
            synthetic=False,
            status="processing",
            added_by=user.uid,
        )
        h.sources.append(source)
        rec = await hs.save(store, rec, h, user.uid, "source.add", source=sid, kind=kind)
    job = await jobs.start(
        store, kind="ingest", household_id=household_id, owner=user.uid, work=_ingest_work(store, household_id, sid, user.uid, data, mime)
    )
    return {"job": job.model_dump(mode="json"), "source_id": sid}


@router.post("/households/{household_id}/sources/{source_id}/extract")
async def reextract(household_id: str, source_id: str, user: User = Depends(current_user), store: Store = Depends(get_store)):
    """Run extraction again on a source (shows the agents at work; reviewed claims are kept)."""
    limit(user, "source", 20)
    rec = await hs.get_record(store, household_id, user.uid)
    h = hs.household_of(rec)
    src = next((s for s in h.sources if s.id == source_id), None)
    if src is None:
        raise HTTPException(404, "No such source.")
    data = await get_blobs().get(src.file) if src.file and src.kind != "evidence" else None
    job = await jobs.start(
        store,
        kind="ingest",
        household_id=household_id,
        owner=user.uid,
        work=_ingest_work(store, household_id, source_id, user.uid, data, src.mime_type),
    )
    return {"job": job.model_dump(mode="json"), "source_id": source_id}


@router.get("/households/{household_id}/sources/{source_id}/file")
async def source_file(household_id: str, source_id: str, user: User = Depends(current_user), store: Store = Depends(get_store)):
    rec = await hs.get_record(store, household_id, user.uid)
    h = hs.household_of(rec)
    src = next((s for s in h.sources if s.id == source_id), None)
    if src is None or not src.file:
        raise HTTPException(404, "No file for this source.")
    data = await get_blobs().get(src.file)
    if data is None and rec.demo:
        from ..domain.household import household_dir

        path = household_dir(rec.demo_source or "perera") / src.file
        data = path.read_bytes() if path.exists() else None
    if data is None:
        raise HTTPException(404, "The file is missing.")
    return Response(content=data, media_type=src.mime_type or "application/octet-stream", headers={"Cache-Control": "private, max-age=300"})


@router.delete("/households/{household_id}/sources/{source_id}")
async def delete_source(household_id: str, source_id: str, user: User = Depends(current_user), store: Store = Depends(get_store)):
    rec = await hs.get_record(store, household_id, user.uid)
    async with hs.lock(rec.id):
        rec = await store.get(household_id)
        h = hs.household_of(rec)
        src = next((s for s in h.sources if s.id == source_id), None)
        if src is None:
            raise HTTPException(404, "No such source.")
        h.sources = [s for s in h.sources if s.id != source_id]
        kept = []
        for c in h.claims:
            remaining = [e for e in c.evidence if e.source_id != source_id]
            if c.evidence and not remaining:
                continue  # every quote came from the deleted source
            c.evidence = remaining
            kept.append(c)
        removed = len(h.claims) - len(kept)
        h.claims = kept
        h.version += 1
        if src.file and not rec.demo:
            await get_blobs().delete_prefix(src.file)
        analysis = hs.quick_analysis(h, rec.analysis)
        rec = await hs.save(store, rec, h, user.uid, "source.delete", source=source_id, claims_removed=removed, analysis=analysis)
    return household_view(rec)


# ---------------------------------------------------------------------- review


class ClaimEdit(BaseModel):
    value: str | None = Field(None, max_length=200)
    date: dt.date | None = None
    schedule: ScheduleSpec | None = None
    window: WindowSpec | None = None


class ReviewAction(BaseModel):
    action: str = Field(pattern="^(accept|reject|dispute|undo|edit)$")
    changes: ClaimEdit | None = None


@router.post("/households/{household_id}/claims/{claim_id}")
async def review_claim(
    household_id: str, claim_id: str, body: ReviewAction, user: User = Depends(current_user), store: Store = Depends(get_store)
):
    rec = await hs.get_record(store, household_id, user.uid)
    async with hs.lock(rec.id):
        rec = await store.get(household_id)
        h = hs.household_of(rec)
        claim = h.claim(claim_id)
        if claim is None:
            raise HTTPException(404, "No such claim.")
        if body.action == "accept":
            if claim.verified is False:
                raise HTTPException(
                    400, "This claim's quote wasn't found in the source, so it can't be used. Edit the source or reject it."
                )
            if claim.issues and claim.verified is not True:
                raise HTTPException(400, "Fix the problems shown on this claim first.")
            claim.review = "accepted"
            for ref in (claim.subject, claim.object):
                for e in h.entities:
                    if e.id == ref:
                        e.proposed = False
        elif body.action == "reject":
            claim.review = "withdrawn"
        elif body.action == "dispute":
            claim.review = "disputed"
        elif body.action == "undo":
            claim.review = "unreviewed"
        elif body.action == "edit" and body.changes:
            update = {k: getattr(body.changes, k) for k in type(body.changes).model_fields if getattr(body.changes, k) is not None}
            note = (claim.note + " " if claim.note else "") + "Edited by the household."
            update |= {"note": note, "derivation": "household_review"}
            idx = h.claims.index(claim)
            h.claims[idx] = claim.model_copy(update=update)
        h.version += 1
        analysis = hs.quick_analysis(h, rec.analysis)
        rec = await hs.save(store, rec, h, user.uid, f"claim.{body.action}", claim=claim_id, analysis=analysis)
    return household_view(rec)


class BulkAccept(BaseModel):
    source_id: str | None = None


@router.post("/households/{household_id}/claims-accept-verified")
async def accept_verified(household_id: str, body: BulkAccept, user: User = Depends(current_user), store: Store = Depends(get_store)):
    """Accept every unreviewed claim whose quotes were verified (optionally for one source)."""
    rec = await hs.get_record(store, household_id, user.uid)
    async with hs.lock(rec.id):
        rec = await store.get(household_id)
        h = hs.household_of(rec)
        n = 0
        for c in h.claims:
            if c.review == "unreviewed" and c.verified and not c.issues and (body.source_id is None or body.source_id in c.source_ids):
                c.review = "accepted"
                n += 1
                for ref in (c.subject, c.object):
                    for e in h.entities:
                        if e.id == ref:
                            e.proposed = False
        h.version += 1
        analysis = hs.quick_analysis(h, rec.analysis)
        rec = await hs.save(store, rec, h, user.uid, "claim.accept_verified", count=n, analysis=analysis)
    return household_view(rec)
