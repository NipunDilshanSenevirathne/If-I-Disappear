"""Storage interfaces. The API only talks to these; memory and Firestore implement them."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field


def now() -> datetime:
    return datetime.now(UTC)


class LogEntry(BaseModel):
    at: datetime = Field(default_factory=now)
    actor: str
    action: str
    detail: dict[str, Any] = Field(default_factory=dict)


class ShareLink(BaseModel):
    """A handover link for the person staying: their card and practice, nothing else."""

    id: str
    token_hash: str  # sha256 of the link token; the token itself is shown once and never stored
    person: str
    responsibilities: list[str]
    created: datetime = Field(default_factory=now)
    created_by: str = ""
    revoked: bool = False
    opened: int = 0


class HistoryPoint(BaseModel):
    """One point on the readiness chart: the result after something changed."""

    at: datetime = Field(default_factory=now)
    action: str
    ready: int
    total: int
    blocked: int = 0
    needs_confirmation: int = 0
    needs_handover: int = 0
    weight_pct: float | None = None


class HouseholdRecord(BaseModel):
    """One household: its knowledge base, its latest analysis and an audit log."""

    id: str
    owner: str
    members: list[str] = Field(default_factory=list)  # other uids allowed to read and practise
    demo: bool = False
    demo_source: str | None = None
    created: datetime = Field(default_factory=now)
    updated: datetime = Field(default_factory=now)
    data: dict[str, Any]
    analysis: dict[str, Any] | None = None
    log: list[LogEntry] = Field(default_factory=list)
    shares: list[ShareLink] = Field(default_factory=list)
    share_hashes: list[str] = Field(default_factory=list)  # active link hashes (for lookup)
    history: list[HistoryPoint] = Field(default_factory=list)
    rev: int = 0

    def can_read(self, uid: str) -> bool:
        return uid == self.owner or uid in self.members

    def add_log(self, actor: str, action: str, **detail: Any) -> None:
        self.log.append(LogEntry(actor=actor, action=action, detail=detail))
        if len(self.log) > 300:
            self.log = self.log[-300:]

    def add_history(self, action: str, summary: dict) -> None:
        """Remember the result after a change (for the readiness chart). Repeats are skipped."""
        point = HistoryPoint(
            action=action,
            ready=int(summary.get("ready", 0)),
            total=int(summary.get("total", 0)),
            blocked=int(summary.get("blocked", 0)),
            needs_confirmation=int(summary.get("needs_confirmation", 0)),
            needs_handover=int(summary.get("needs_handover", 0)),
            weight_pct=summary.get("ready_pct"),
        )
        last = self.history[-1] if self.history else None
        same = last is not None and (last.ready, last.total, last.blocked, last.needs_confirmation, last.needs_handover) == (
            point.ready,
            point.total,
            point.blocked,
            point.needs_confirmation,
            point.needs_handover,
        )
        if same and last.action == action:
            return
        self.history.append(point)
        if len(self.history) > 120:
            self.history = self.history[-120:]


class Job(BaseModel):
    id: str
    household_id: str
    owner: str
    kind: str  # ingest | analyze | grade
    status: str = "queued"  # queued | running | done | error
    created: datetime = Field(default_factory=now)
    updated: datetime = Field(default_factory=now)
    progress: list[dict[str, Any]] = Field(default_factory=list)  # trace of workflow steps
    result: dict[str, Any] | None = None
    error: str | None = None


class ConflictError(Exception):
    """The record changed since it was read (optimistic concurrency)."""


# A household is stored as one Firestore document (limit 1 MiB). Stay well below it,
# and say so plainly instead of failing deep inside the database client.
MAX_RECORD_BYTES = 900_000


class RecordTooLarge(ValueError):
    pass


def check_size(record: HouseholdRecord) -> None:
    size = len(record.model_dump_json())
    if size > MAX_RECORD_BYTES:
        raise RecordTooLarge(
            f"This household has grown too large to save ({size // 1000} kB). Remove a few long sources or old attempts and try again."
        )


class Store(Protocol):
    async def get(self, household_id: str) -> HouseholdRecord | None: ...

    async def put(self, record: HouseholdRecord, *, expected_rev: int | None = None) -> HouseholdRecord: ...

    async def delete(self, household_id: str) -> None: ...

    async def list_for(self, uid: str) -> list[HouseholdRecord]: ...

    async def find_demo(self, uid: str, source: str | None = None) -> HouseholdRecord | None: ...

    async def find_by_share(self, token_hash: str) -> HouseholdRecord | None: ...

    async def get_meta(self, key: str) -> dict | None: ...

    async def put_meta(self, key: str, value: dict) -> None: ...

    async def get_job(self, job_id: str) -> Job | None: ...

    async def put_job(self, job: Job) -> Job: ...


class BlobStore(Protocol):
    async def put(self, key: str, data: bytes, mime_type: str) -> str: ...

    async def get(self, key: str) -> bytes | None: ...

    async def delete_prefix(self, prefix: str) -> None: ...
