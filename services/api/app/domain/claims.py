"""Entities, claims and evidence: the household's reviewable knowledge base.

The AI proposes claims; the household reviews them; only accepted claims are
compiled into the engine model. Every claim points at the exact source text it
came from (a verbatim quote plus a locator), and records how it was derived.
"""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EntityKind = Literal["person", "responsibility", "resource", "route", "fact", "organization"]
ResourceKindName = Literal[
    "phone_number", "handset", "contact", "document", "location", "account", "vehicle", "permit", "service", "note", "item"
]

Predicate = Literal[
    # who does what
    "DOES",  # person -> responsibility: already does it regularly
    "CAN_DO",  # person -> responsibility: value yes | no | unsure
    "IMPORTANCE",  # responsibility: value 1 | 2 | 3
    "SCHEDULE",  # responsibility: schedule (+ window)
    "LEAD_TIME",  # responsibility: value days
    "KEY_STEP",  # responsibility: value = the key step to show
    "HANDOVER_LEVEL",  # responsibility: value light | standard | critical (household-reviewed)
    "AMOUNT",  # responsibility: value = amount as written
    # routes
    "ROUTE",  # responsibility -> route
    "ROUTE_NEEDS",  # route -> resource
    "ROUTE_NEEDS_VALID",  # route -> resource (permit)
    "ROUTE_NEEDS_FACT",  # route -> fact
    "ROUTE_PERFORMER",  # route -> person
    "ROUTE_WINDOW",  # route: window
    "ROUTE_FLEXIBLE",  # route: value days
    "ROUTE_WEEKDAYS",  # route: value "MO,TU,WE,TH,FR"
    "NEEDS",  # responsibility -> resource (every route)
    "NEEDS_VALID",  # responsibility -> resource (every route)
    # resources
    "HOLDS",  # person -> resource
    "STORED_ON",  # resource -> container resource
    "SHARED_WITH",  # resource -> person
    "REQUIRES_RESOURCE",  # resource -> resource
    "NOTIFIES",  # resource -> responsibility (a reminder or schedule source)
    "MENTIONED_ON",  # resource -> document resource (appears, no stated role)
    "VALID_UNTIL",  # resource: date
    "RENEWS",  # responsibility -> resource
    "STOPS_DURING_ABSENCE",  # resource: value decided | maybe
    # people's time
    "BUSY",  # person: schedule + window + value label
    "UNAVAILABLE",  # person: date .. end_date (exclusive) + value label
    "FREE_ON",  # person -> commitment-id-as-value: date (agreed to be free that day)
    # conditions
    "FACT",  # fact: value yes | no | unsure
    "ENABLES",  # fact: value = how to make it true (label)
    # safety
    "KNOWS_SECRET",  # person -> resource: a secret exists (never the value)
]

Derivation = Literal["user_statement", "document", "model_inference", "external_confirmation", "observation", "household_review"]
Review = Literal["unreviewed", "accepted", "disputed", "superseded", "withdrawn"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScheduleSpec(Model):
    freq: Literal["once", "daily", "weekly", "monthly", "yearly", "ongoing"]
    interval: int = 1
    weekdays: list[Literal["MO", "TU", "WE", "TH", "FR", "SA", "SU"]] = Field(default_factory=list)
    monthday: int | None = None
    anchor: dt.date | None = None


class WindowSpec(Model):
    start: str  # "HH:MM"
    end: str


class EvidenceRef(Model):
    source_id: str
    quote: str
    locator: str | None = None


class Entity(Model):
    id: str
    kind: EntityKind
    name: str
    names: dict[str, str] = Field(default_factory=dict)  # older data only (display names in other languages)
    aliases: list[str] = Field(default_factory=list)
    resource_kind: ResourceKindName | None = None
    identifier: str | None = None
    role: str | None = None  # person: leaver | backup | household | helper
    minor: bool = False
    generic: bool = False
    category: str | None = None
    proposed: bool = False  # created by the extractor; becomes real when a claim using it is accepted


class Claim(Model):
    id: str
    predicate: Predicate
    subject: str
    object: str | None = None
    value: str | None = None
    date: dt.date | None = None
    end_date: dt.date | None = None
    schedule: ScheduleSpec | None = None
    window: WindowSpec | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)
    derivation: Derivation = "user_statement"
    review: Review = "unreviewed"
    stated_by: str | None = None
    created_by: Literal["extractor", "household", "fixture", "evidence", "system"] = "extractor"
    note: str | None = None
    fixed: bool = False  # BUSY: the person can't move this commitment (booked, paid, an exam)
    minutes: int | None = None  # ENABLES: rough time it takes
    confidence: float | None = None  # extractor's own confidence (shown, never used to decide)
    verified: bool | None = None  # quotes checked against the source (None: not checked yet)
    issues: list[str] = Field(default_factory=list)  # why it can't be used yet
    source_ids: list[str] = Field(default_factory=list)  # where it was extracted from


class Source(Model):
    id: str
    kind: Literal["voice", "image", "pdf", "text", "practice", "evidence"]
    title: str
    language: str = "en"
    speaker: str | None = None
    text: str = ""  # transcript / OCR / typed text (already redacted)
    text_original: str | None = None  # older data only (the app is English-only now)
    file: str | None = None  # path or storage key of the original file
    mime_type: str | None = None
    observed: dt.date | None = None
    synthetic: bool = True
    visibility: Literal["household", "private"] = "household"
    redactions: int = 0
    status: Literal["ready", "processing", "error"] = "ready"
    summary: str | None = None
    error: str | None = None
    added_by: str | None = None


class ProcedureStep(Model):
    id: str
    text: str
    texts: dict[str, str] = Field(default_factory=dict)  # older data only (translations)
    hint: str | None = None  # a question that points at the step without giving it away
    critical: bool = False
    keywords: list[str] = Field(default_factory=list)  # used only by the offline grader


class Procedure(Model):
    responsibility: str
    version: int = 1
    approved: bool = True
    steps: list[ProcedureStep]
    scenario_prompt: str = ""
    scenario_prompts: dict[str, str] = Field(default_factory=dict)  # older data only


class HouseholdSettings(Model):
    id: str
    name: str
    timezone: str = "Asia/Colombo"
    leaver: str
    departure: dt.date
    destination: str | None = None  # where the leaver is going (shown on the boarding pass)
    absence: Literal["travel", "hospital", "other"] = "travel"  # what kind of absence (only changes an icon)
    airport_from: str = "CMB"
    airport_to: str | None = None
    horizon_days: int = 90
    assessment_date: dt.date
    languages: list[str] = Field(default_factory=lambda: ["en"])
    synthetic: bool = True
    card_entries: list[str] = Field(default_factory=list)
    in_scope: list[str] | None = None  # None = all responsibilities
    budget_minutes: int = 60


class PracticeAttempt(Model):
    """One teach-back attempt, graded against the approved steps."""

    id: str
    person: str
    responsibility: str
    language: str = "en"
    created: dt.date | None = None
    transcript: str = ""
    hints: list[str] = Field(default_factory=list)
    covered: list[str] = Field(default_factory=list)
    missed: list[str] = Field(default_factory=list)
    unsafe: list[str] = Field(default_factory=list)  # statements that contradict an approved step
    result: Literal["unassisted", "practiced_with_help", "not_yet"] = "not_yet"
    grader: str = "fixture"  # fixture | gemini | keyword
    feedback: str | None = None


class HandoverEvent(Model):
    """Evidence about a person and a responsibility that is not a claim about the world:
    viewing steps, a practice attempt result, a witnessed demonstration."""

    id: str
    person: str
    responsibility: str
    kind: Literal["viewed", "practice", "demonstration"]
    level: Literal["viewed", "practiced_with_help", "unassisted", "self_reported", "witnessed"]
    attempt_id: str | None = None
    witness: str | None = None
    note: str | None = None
    created: dt.date | None = None
