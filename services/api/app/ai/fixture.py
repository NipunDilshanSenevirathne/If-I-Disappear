"""Fixture-mode answers: replayed, never invented.

* Extraction of a demo source returns the household's reviewed claims for that
  source (with only that source's quotes), exactly as a live run should.
* A sample file (one of the rendered SAMPLE documents) is recognised by its
  SHA-256 and replayed; any other file gets an honest "live AI is off" answer.
* The challenger is a small rule-based reviewer: it questions findings that lean
  on inferred claims and upholds the rest. The UI labels it "offline review".
"""

from __future__ import annotations

import hashlib
from functools import lru_cache

from ..domain.claims import Claim
from ..domain.household import FIXTURES, available_households, load_household
from ..engine.discover import Finding
from .schemas import (
    ChallengeItem,
    ChallengeReport,
    Extraction,
    ProposedClaim,
    ProposedEntity,
    ProposedSchedule,
    ProposedWindow,
    Reading,
    Transcript,
)

OFFLINE_NOTE = "Live AI is off, so new sources can't be read or analysed. Add a GEMINI_API_KEY to turn it on."


@lru_cache
def sample_index() -> dict[str, tuple[str, str]]:
    """sha256 of every rendered sample file -> (household id, source id)."""
    index: dict[str, tuple[str, str]] = {}
    for hid in available_households():
        files = FIXTURES / hid / "files"
        if not files.is_dir():
            continue
        for path in files.iterdir():
            if path.is_file():
                index[hashlib.sha256(path.read_bytes()).hexdigest()] = (hid, path.stem)
    return index


def recognise(data: bytes) -> tuple[str, str] | None:
    return sample_index().get(hashlib.sha256(data).hexdigest())


@lru_cache
def _fixture(hid: str):
    return load_household(hid)


def fixture_source(hid: str, sid: str):
    try:
        h = _fixture(hid)
    except FileNotFoundError:
        return None
    return next((s for s in h.sources if s.id == sid), None)


def replay_reading(hid: str, sid: str) -> Reading:
    src = fixture_source(hid, sid)
    if src is None:
        return Reading(kind="other", text="")
    kind = "photo" if src.text.startswith("[Photo]") else "document"
    return Reading(kind=kind, text=src.text, is_sample=True)


def replay_transcript(hid: str, sid: str) -> Transcript:
    src = fixture_source(hid, sid)
    if src is None:
        return Transcript(text="")
    return Transcript(text=src.text, secrets_removed=src.redactions)


def _proposed(c: Claim, sid: str) -> ProposedClaim | None:
    quotes = [e.quote for e in c.evidence if e.source_id == sid]
    if not quotes:
        return None
    return ProposedClaim(
        predicate=c.predicate,
        subject=c.subject,
        object=c.object,
        value=c.value,
        date=c.date.isoformat() if c.date else None,
        end_date=c.end_date.isoformat() if c.end_date else None,
        schedule=(
            ProposedSchedule(
                freq=c.schedule.freq,
                interval=c.schedule.interval,
                weekdays=list(c.schedule.weekdays),
                monthday=c.schedule.monthday,
                anchor=c.schedule.anchor.isoformat() if c.schedule.anchor else None,
            )
            if c.schedule
            else None
        ),
        window=ProposedWindow(start=c.window.start, end=c.window.end) if c.window else None,
        fixed=c.fixed,
        quotes=quotes,
        derivation=c.derivation if c.derivation in ("user_statement", "document", "model_inference") else "user_statement",
        note=c.note,
        confidence=0.7 if c.derivation == "model_inference" else 0.95,
    )


def replay_extraction(hid: str, sid: str, known_ids: set[str]) -> Extraction:
    """The reviewed claims for one demo source, as the extractor should have proposed them."""
    try:
        h = _fixture(hid)
    except FileNotFoundError:
        return Extraction(source_summary=OFFLINE_NOTE, questions=[OFFLINE_NOTE])
    src = next((s for s in h.sources if s.id == sid), None)
    if src is None:
        return Extraction(source_summary=OFFLINE_NOTE, questions=[OFFLINE_NOTE])
    claims = [p for c in h.claims if (p := _proposed(c, sid))]
    used = {x for p in claims for x in (p.subject, p.object) if x}
    entities = [
        ProposedEntity(
            ref=e.id,
            kind=e.kind,
            name=e.name,
            resource_kind=e.resource_kind,
            identifier=e.identifier,
            minor=e.minor,
        )
        for e in h.entities
        if e.id in used and e.id not in known_ids
    ]
    return Extraction(source_summary=f"Replayed from the reviewed demo data for {src.title}.", entities=entities, claims=claims)


def offline_challenge(findings: list[Finding], claims: dict[str, Claim]) -> ChallengeReport:
    """A rule-based stand-in for the challenger: question what leans on inference."""
    items = []
    for f in findings:
        weak = [cid for cid in f.claim_ids if cid in claims and claims[cid].derivation == "model_inference"]
        single = [cid for cid in f.claim_ids if cid in claims and len({e.source_id for e in claims[cid].evidence}) == 1]
        if weak:
            c = claims[weak[0]]
            question = f"Is this right: {c.note.rstrip('.')}?" if c.note else "Can you confirm the inferred details?"
            items.append(
                ChallengeItem(
                    finding_id=f.id,
                    verdict="question",
                    explanation=f"This leans on something we inferred rather than something you said: {c.note or c.predicate}.",
                    weak_claims=weak,
                    question=question,
                )
            )
        else:
            first = f.summary.split(". ")[0].rstrip(".") + "."
            items.append(ChallengeItem(finding_id=f.id, verdict="uphold", explanation=first, weak_claims=single[:3]))
    return ChallengeReport(items=items)
