"""Add a responsibility by hand, without any AI.

A family that would rather type than talk (or a visitor whose free AI allowance
is used up) fills in a short form. Code turns it into the same reviewed facts
the AI would have proposed, each quoting a sentence of a "typed by you" note,
so everything downstream (the engine, findings, the plan, the card) works the
same way and every fact still points at where it came from.
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from typing import Literal

from pydantic import BaseModel, Field

from ..ai.redact import redact
from ..domain.claims import Claim, Entity, EvidenceRef, ScheduleSpec, Source, WindowSpec
from ..domain.household import Household

WEEKDAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
DAY_NAMES = dict(zip(WEEKDAYS, ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], strict=True))
THING_KINDS = Literal["document", "contact", "account", "item", "vehicle", "phone_number", "location", "service"]


class NeedIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: THING_KINDS = "item"
    held_by: str | None = None  # a person id: who has it now
    taker_has_it: bool = False  # the person taking over already has it (or a copy)


class ResponsibilityIn(BaseModel):
    label: str = Field(min_length=3, max_length=90)
    category: str = Field("household", max_length=30)
    freq: Literal["once", "weekly", "monthly", "ongoing"] = "monthly"
    interval: int = Field(1, ge=1, le=12)
    weekdays: list[Literal["MO", "TU", "WE", "TH", "FR", "SA", "SU"]] = Field(default_factory=list, max_length=7)
    monthday: int | None = Field(None, ge=1, le=31)
    date: dt.date | None = None  # once: the date; weekly/monthly: the next one, if known
    window_start: str | None = Field(None, pattern=r"^\d{1,2}:\d{2}$")
    window_end: str | None = Field(None, pattern=r"^\d{1,2}:\d{2}$")
    usual: str | None = None  # who usually does it (default: the person leaving)
    taker: str | None = None  # who will do it during the absence
    agreed: Literal["yes", "unsure", "no"] = "unsure"
    importance: int = Field(2, ge=1, le=3)
    needs: list[NeedIn] = Field(default_factory=list, max_length=8)
    key_step: str | None = Field(None, max_length=200)


class ManualError(ValueError):
    pass


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40] or "item"


def _schedule_phrase(body: ResponsibilityIn) -> str:
    if body.freq == "once":
        return f"once, on {body.date.strftime('%d %B %Y')}" if body.date else "once"
    if body.freq == "ongoing":
        return "all the time (it's ongoing)"
    if body.freq == "weekly":
        days = " and ".join(DAY_NAMES[d] for d in body.weekdays) or "a weekday"
        every = "every" if body.interval == 1 else f"every {body.interval} weeks on"
        return f"{every} {days}"
    day = body.monthday or (body.date.day if body.date else None)
    every = "every month" if body.interval == 1 else f"every {body.interval} months"
    return f"{every} on day {day}" if day else every


def add_responsibility(h: Household, body: ResponsibilityIn, actor: str) -> dict:
    ents = h.entity_map()
    people = {e.id: e for e in h.entities if e.kind == "person"}
    leaver = h.settings.leaver
    usual = body.usual or leaver
    if usual not in people:
        raise ManualError("Choose who usually does this.")
    if body.taker is not None and (body.taker not in people or people[body.taker].minor):
        raise ManualError("Choose an adult to take this over.")
    if body.freq == "once" and body.date is None:
        raise ManualError("Pick the date for a one-off task.")
    if body.freq == "weekly" and not body.weekdays:
        raise ManualError("Pick the day of the week.")
    if (body.window_start is None) != (body.window_end is None):
        raise ManualError("Give both a start and an end time, or neither.")
    for need in body.needs:
        if need.held_by is not None and need.held_by not in people:
            raise ManualError("Choose who has each thing.")

    label = redact(body.label.strip()).text
    rid = f"r_{_slug(label)}"
    n = 2
    while rid in ents:
        rid, n = f"r_{_slug(label)}_{n}", n + 1
    h.entities.append(Entity(id=rid, kind="responsibility", name=label[:1].upper() + label[1:], category=body.category or "household"))

    sid = f"T{len([s for s in h.sources if s.id.startswith('T')]) + 1:02d}-{uuid.uuid4().hex[:4]}"
    sentences: list[tuple[str, dict]] = []
    name = {pid: p.name for pid, p in people.items()}

    sentences.append((f"{name[usual]} usually does this: {label}.", {"predicate": "DOES", "subject": usual, "object": rid}))
    schedule = ScheduleSpec(
        freq=body.freq,
        interval=body.interval,
        weekdays=list(body.weekdays),
        monthday=body.monthday or (body.date.day if body.freq == "monthly" and body.date else None),
        anchor=body.date,
    )
    window = WindowSpec(start=body.window_start, end=body.window_end) if body.window_start and body.window_end else None
    when = _schedule_phrase(body) + (f", between {body.window_start} and {body.window_end}" if window else "")
    sentences.append((f"It happens {when}.", {"predicate": "SCHEDULE", "subject": rid, "schedule": schedule, "window": window}))
    sentences.append(
        (f"How much it matters: {body.importance} out of 3.", {"predicate": "IMPORTANCE", "subject": rid, "value": str(body.importance)})
    )
    if body.taker:
        who = name[body.taker]
        text = {
            "yes": f"{who} has agreed to do it while {name[leaver]} is away.",
            "unsure": f"{who} might do it while {name[leaver]} is away, but hasn't agreed yet.",
            "no": f"{who} can't do it while {name[leaver]} is away.",
        }[body.agreed]
        sentences.append((text, {"predicate": "CAN_DO", "subject": body.taker, "object": rid, "value": body.agreed}))

    for need in body.needs:
        thing = redact(need.name.strip()).text
        existing = next((e for e in h.entities if e.kind == "resource" and e.name.lower() == thing.lower()), None)
        if existing is None:
            xid = f"x_{_slug(thing)}"
            n = 2
            while xid in h.entity_map():
                xid, n = f"x_{_slug(thing)}_{n}", n + 1
            h.entities.append(Entity(id=xid, kind="resource", name=thing, resource_kind=need.kind))
        else:
            xid = existing.id
        sentences.append((f"It needs {thing}.", {"predicate": "NEEDS", "subject": rid, "object": xid}))
        if need.held_by:
            sentences.append((f"{name[need.held_by]} has {thing}.", {"predicate": "HOLDS", "subject": need.held_by, "object": xid}))
        if need.taker_has_it and body.taker and body.taker != need.held_by:
            sentences.append((f"{name[body.taker]} has {thing} too.", {"predicate": "SHARED_WITH", "subject": xid, "object": body.taker}))
    if body.key_step:
        step = redact(body.key_step.strip()).text.rstrip(".")
        sentences.append((f"The step that matters most: {step}.", {"predicate": "KEY_STEP", "subject": rid, "value": step}))

    text = " ".join(s for s, _ in sentences)
    h.sources.append(
        Source(
            id=sid,
            kind="text",
            title=f"Typed in: {label}",
            text=text,
            speaker=None,
            observed=dt.date.today(),
            synthetic=h.settings.synthetic,
            status="ready",
            summary=f"Added by hand: {label}.",
            added_by=actor,
        )
    )
    added = []
    for i, (sentence, fields) in enumerate(sentences, start=1):
        claim = Claim(
            id=f"{sid}-{i:02d}",
            evidence=[EvidenceRef(source_id=sid, quote=sentence)],
            derivation="household_review",
            review="accepted",
            created_by="household",
            verified=True,
            source_ids=[sid],
            **fields,
        )
        h.claims.append(claim)
        added.append(claim.id)
    h.version += 1
    return {"responsibility": rid, "source": sid, "claims": added}
