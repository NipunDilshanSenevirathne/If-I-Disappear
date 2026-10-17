"""Structured outputs requested from Gemini (response_schema).

The model fills these; code validates and decides. Nothing here is trusted until
it passes the quote verifier and the household's review.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..domain.claims import Predicate

Weekday = Literal["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


class Transcript(BaseModel):
    text: str = Field(description="Exactly what was said, word for word")
    secrets_removed: int = Field(0, description="How many secret values were replaced with [secret removed]")


class Reading(BaseModel):
    kind: Literal["document", "photo", "screenshot", "handwritten", "other"]
    text: str = Field(description="Visible text, one printed line per line; [Page N] lines for PDFs; [Photo] for photos")
    is_sample: bool = False
    secrets_removed: int = 0


class ProposedEntity(BaseModel):
    ref: str = Field(description="new:<short_snake_name> for a new entity")
    kind: Literal["person", "responsibility", "resource", "route", "fact", "organization"]
    name: str
    resource_kind: (
        Literal["phone_number", "handset", "contact", "document", "location", "account", "vehicle", "permit", "service", "note", "item"]
        | None
    ) = None
    identifier: str | None = Field(None, description="Masked identifier, e.g. 077-XXX-0101")
    minor: bool = False


class ProposedSchedule(BaseModel):
    freq: Literal["once", "daily", "weekly", "monthly", "yearly", "ongoing"]
    interval: int = 1
    weekdays: list[Weekday] = Field(default_factory=list)
    monthday: int | None = None
    anchor: str | None = Field(None, description="ISO date of the next known occurrence")


class ProposedWindow(BaseModel):
    start: str = Field(description="HH:MM, 24-hour")
    end: str = Field(description="HH:MM, 24-hour")


class ProposedClaim(BaseModel):
    predicate: Predicate
    subject: str
    object: str | None = None
    value: str | None = None
    date: str | None = None
    end_date: str | None = None
    schedule: ProposedSchedule | None = None
    window: ProposedWindow | None = None
    fixed: bool = False
    quotes: list[str] = Field(description="Exact quotes from the source that prove the claim")
    derivation: Literal["user_statement", "document", "model_inference"] = "user_statement"
    note: str | None = None
    confidence: float = Field(0.8, ge=0, le=1)


class Extraction(BaseModel):
    source_summary: str = Field(description="One sentence: what this source is about")
    entities: list[ProposedEntity] = Field(default_factory=list)
    claims: list[ProposedClaim] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


class ChallengeItem(BaseModel):
    finding_id: str
    verdict: Literal["uphold", "narrow", "question"]
    explanation: str
    drop: list[str] = Field(default_factory=list, description="Responsibility ids to drop (narrow only)")
    because_claims: list[str] = Field(default_factory=list)
    weak_claims: list[str] = Field(default_factory=list, description="Claim ids that are inferred or single-sourced")
    question: str | None = None


class ChallengeReport(BaseModel):
    items: list[ChallengeItem]


class StepGrade(BaseModel):
    step_id: str
    status: Literal["covered", "partly", "missed", "wrong"]
    evidence: str | None = None


class PracticeGrade(BaseModel):
    steps: list[StepGrade]
    hints_given: int = 0
    unsafe: list[str] = Field(default_factory=list)
    feedback: str = ""
