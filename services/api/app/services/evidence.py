"""Evidence changes the household's state; plans never do.

A plan step says what *would* happen. When the household records evidence for a
step (an agreement, a photo, a screenshot, a witnessed demonstration), it is
turned into ordinary claims and handover events with a quote from an evidence
record, using the step's typed effects. The next analysis then reflects it.
Practice steps are evidenced only by a graded practice attempt.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from ..domain.claims import Claim, EvidenceRef, HandoverEvent, PracticeAttempt, Source
from ..domain.household import Household
from ..engine import effects as fx
from ..engine.evaluate import evaluate
from ..engine.repair import Step, plan
from ..engine.text import fmt_day

EVIDENCE_KINDS = ("AGREEMENT", "PHOTO", "SCREENSHOT", "SELF_REPORT", "PROVIDER_CONFIRMATION", "WITNESS", "DOCUMENT", "APP", "STATEMENT")


class EvidenceError(ValueError):
    pass


@dataclass
class EvidenceInput:
    step_id: str
    kind: str
    note: str | None = None
    witness: str | None = None
    new_date: date | None = None
    file_key: str | None = None
    mime_type: str | None = None
    on: date | None = None


def plan_steps(h: Household) -> dict[str, Step]:
    """Every step of every candidate bundle, by id (recomputed deterministically)."""
    c = h.compile()
    p = plan(c.world, c.scenario, evaluate(c.world, c.scenario), budget_minutes=10_000)
    steps: dict[str, Step] = {}
    for b in p.candidates:
        for s in b.steps:
            steps.setdefault(s.id, s)
    return steps


def _name(h: Household, eid: str | None) -> str:
    ents = h.entity_map()
    return ents[eid].name if eid and eid in ents else (eid or "")


def _make_source(h: Household, title: str, text: str, inp: EvidenceInput, actor: str) -> Source:
    sid = f"EV-{uuid.uuid4().hex[:6]}"
    src = Source(
        id=sid,
        kind="evidence",
        title=title,
        text=text,
        observed=inp.on or date.today(),
        synthetic=h.settings.synthetic,
        file=inp.file_key,
        mime_type=inp.mime_type,
        added_by=actor,
    )
    h.sources.append(src)
    return src


def _claim(h: Household, src: Source, quote: str, **kw) -> Claim:
    c = Claim(
        id=f"{src.id}-{len([x for x in h.claims if x.id.startswith(src.id)]) + 1:02d}",
        evidence=[EvidenceRef(source_id=src.id, quote=quote, locator="line 1")],
        review="accepted",
        created_by="evidence",
        verified=True,
        source_ids=[src.id],
        **kw,
    )
    h.claims.append(c)
    return c


def record_step_evidence(h: Household, inp: EvidenceInput, actor: str) -> dict:
    if inp.kind not in EVIDENCE_KINDS:
        raise EvidenceError(f"Unknown evidence type {inp.kind}.")
    steps = plan_steps(h)
    step = steps.get(inp.step_id)
    if step is None:
        raise EvidenceError("That step isn't part of the current plan any more. Refresh the plan and try again.")
    if step.kind == "PRACTICE":
        raise EvidenceError("A practice step is recorded by practising: start the practice for this task.")
    on = inp.on or date.today()
    day = fmt_day(on) + on.strftime(" %Y")
    changes: list[str] = []
    created: list[str] = []
    events: list[str] = []
    record: Source | None = None

    def _new_source(h: Household, title: str, text: str, inp: EvidenceInput, actor: str) -> Source:
        """One source per recorded step, however many facts it confirms (each quotes its own sentence)."""
        nonlocal record
        if record is None:
            record = _make_source(h, title, text, inp, actor)
        else:
            sentence = text.split(". ", 1)[1] if ". " in text else text
            record.text = f"{record.text} {sentence}"
        return record

    for e in step.effects:
        if e.kind == fx.WILLING:
            label = h.entity_map()[e.responsibility].name
            sentence = f"{_name(h, e.person)} said yes to: {label}."
            src = _new_source(h, f"{_name(h, e.person)}'s agreement", f"Agreement recorded in the app on {day}. {sentence}", inp, actor)
            created.append(
                _claim(
                    h, src, sentence, predicate="CAN_DO", subject=e.person, object=e.responsibility, value="yes", derivation="observation"
                ).id
            )
            changes.append(f"{_name(h, e.person)} agreed to {label}.")
        elif e.kind == fx.STORE_ON:
            sentence = f"{_name(h, e.resource)} is saved on {_name(h, e.container)}."
            src = _new_source(h, "Contact saved", f"{inp.kind.title().replace('_', ' ')} recorded on {day}. {sentence}", inp, actor)
            created.append(
                _claim(h, src, sentence, predicate="STORED_ON", subject=e.resource, object=e.container, derivation="observation").id
            )
            changes.append(sentence)
        elif e.kind == fx.SHARE:
            sentence = f"{_name(h, e.person)} now has access to {_name(h, e.resource)}."
            src = _new_source(h, "Shared", f"{inp.kind.title().replace('_', ' ')} recorded on {day}. {sentence}", inp, actor)
            created.append(
                _claim(h, src, sentence, predicate="SHARED_WITH", subject=e.resource, object=e.person, derivation="observation").id
            )
            changes.append(sentence)
        elif e.kind == fx.FACT_TRUE:
            sentence = f"Confirmed: {_name(h, e.fact)}."
            derivation = "external_confirmation" if inp.kind == "PROVIDER_CONFIRMATION" else "observation"
            src = _new_source(h, "Confirmation", f"{inp.kind.title().replace('_', ' ')} recorded on {day}. {sentence}", inp, actor)
            created.append(_claim(h, src, sentence, predicate="FACT", subject=e.fact, value="yes", derivation=derivation).id)
            changes.append(sentence)
        elif e.kind == fx.COMMITMENT_OFF:
            busy_claim = (e.commitment or "").removeprefix("busy:")
            person = next((c.subject for c in h.claims if c.id == busy_claim), None)
            if person is None:
                continue
            sentence = f"{_name(h, person)} will be free on {fmt_day(e.day)}."
            src = _new_source(h, "Day kept free", f"Agreement recorded in the app on {day}. {sentence}", inp, actor)
            created.append(
                _claim(h, src, sentence, predicate="FREE_ON", subject=person, value=busy_claim, date=e.day, derivation="observation").id
            )
            changes.append(sentence)
        elif e.kind == fx.VALID_UNTIL:
            new_date = inp.new_date or e.new_date
            if new_date is None:
                raise EvidenceError("Add the new expiry date from the renewed document.")
            sentence = f"{_name(h, e.resource)} is now valid until {new_date.isoformat()}."
            src = _new_source(h, "Renewed document", f"Renewal recorded on {day}. {sentence}", inp, actor)
            derivation = "document" if inp.file_key else "household_review"
            for c in h.claims:
                if c.predicate == "VALID_UNTIL" and c.subject == e.resource and c.review == "accepted":
                    c.review = "superseded"
            created.append(_claim(h, src, sentence, predicate="VALID_UNTIL", subject=e.resource, date=new_date, derivation=derivation).id)
            changes.append(sentence)
        elif e.kind == fx.DROP_ASSUMPTION:
            claim_id = (e.assumption or "").removeprefix("assume:")
            for c in h.claims:
                if c.id == claim_id:
                    c.review = "withdrawn"
                    changes.append(f"Changed the plan: {_name(h, c.subject)} will be kept going.")
        elif e.kind == fx.CARD:
            if e.responsibility not in h.settings.card_entries:
                h.settings = h.settings.model_copy(update={"card_entries": h.settings.card_entries + [e.responsibility]})
            changes.append(f"Added '{_name(h, e.responsibility)}' to the Continuity Card.")
        elif e.kind == fx.UNDERSTANDING:
            if (e.level or 0) > 1:
                raise EvidenceError("Explaining it back is recorded by practising.")
            ev = HandoverEvent(
                id=f"H-{uuid.uuid4().hex[:6]}", person=e.person, responsibility=e.responsibility, kind="viewed", level="viewed", created=on
            )
            h.handover_events.append(ev)
            events.append(ev.id)
            changes.append(f"{_name(h, e.person)} has seen the steps for {_name(h, e.responsibility)}.")
        elif e.kind == fx.PRACTICAL:
            witness = inp.witness
            if not witness or witness == e.person:
                raise EvidenceError("Someone else has to watch the key step and confirm it.")
            ev = HandoverEvent(
                id=f"H-{uuid.uuid4().hex[:6]}",
                person=e.person,
                responsibility=e.responsibility,
                kind="demonstration",
                level="witnessed",
                witness=witness,
                note=inp.note,
                created=on,
            )
            h.handover_events.append(ev)
            events.append(ev.id)
            changes.append(f"{_name(h, witness)} watched {_name(h, e.person)} do the key step.")
    h.version += 1
    return {"step": step.id, "changes": changes, "claims": created, "events": events}


def record_attempt(h: Household, attempt: PracticeAttempt) -> HandoverEvent | None:
    h.practice_attempts.append(attempt)
    event = None
    if attempt.result in ("unassisted", "practiced_with_help"):
        event = HandoverEvent(
            id=f"H-{uuid.uuid4().hex[:6]}",
            person=attempt.person,
            responsibility=attempt.responsibility,
            kind="practice",
            level=attempt.result,
            attempt_id=attempt.id,
            created=attempt.created,
        )
        h.handover_events.append(event)
    h.version += 1
    return event


def answer_finding(h: Household, finding: dict, answer: dict, actor: str) -> list[str]:
    """Answer the question a finding asks. Supported: contradictions (pick a value),
    not-asked questions (yes/no per person) and the reviewer's questions (confirm or dispute)."""
    changes: list[str] = []
    kind = finding.get("kind")
    on = date.today()
    if kind == "CONTRADICTION":
        keep = answer.get("keep_claim")
        ids = finding.get("claim_ids", [])
        if keep not in ids:
            raise EvidenceError("Pick one of the values your sources gave.")
        for c in h.claims:
            if c.id in ids and c.id != keep and c.review == "accepted":
                c.review = "superseded"
                changes.append(f"Set aside '{c.value}'.")
    elif kind == "NOT_ASKED":
        person, resp, value = answer.get("person"), answer.get("responsibility"), answer.get("value")
        if value not in ("yes", "no", "unsure"):
            raise EvidenceError("Answer yes, no or not sure.")
        label = _name(h, resp)
        sentence = f"{_name(h, person)} answered '{value}' to: {label}."
        inp = EvidenceInput(step_id="answer", kind="AGREEMENT", on=on)
        src = _make_source(h, "Answer", f"Answer recorded in the app on {on.isoformat()}. {sentence}", inp, actor)
        for c in h.claims:
            if c.predicate == "CAN_DO" and c.subject == person and c.object == resp and c.review == "accepted":
                c.review = "superseded"
        _claim(h, src, sentence, predicate="CAN_DO", subject=person, object=resp, value=value, derivation="observation")
        changes.append(sentence)
    else:
        confirm = answer.get("confirm")
        weak = (finding.get("challenge") or {}).get("weak_claims", [])
        for c in h.claims:
            if c.id in weak:
                if confirm:
                    c.derivation = "household_review"
                    c.note = (c.note + " " if c.note else "") + "Confirmed by the household."
                    changes.append(f"Confirmed {c.id}.")
                else:
                    c.review = "disputed"
                    changes.append(f"Disputed {c.id}; it won't be used.")
    h.version += 1
    return changes
