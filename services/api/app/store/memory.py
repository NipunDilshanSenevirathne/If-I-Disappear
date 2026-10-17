"""In-memory store for local development and tests. Data is lost on restart."""

from __future__ import annotations

import asyncio
import copy

from .base import ConflictError, HouseholdRecord, Job, check_size, now


class MemoryStore:
    def __init__(self) -> None:
        self._households: dict[str, HouseholdRecord] = {}
        self._jobs: dict[str, Job] = {}
        self._meta: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    async def get(self, household_id: str) -> HouseholdRecord | None:
        rec = self._households.get(household_id)
        return rec.model_copy(deep=True) if rec else None

    async def put(self, record: HouseholdRecord, *, expected_rev: int | None = None) -> HouseholdRecord:
        async with self._lock:
            current = self._households.get(record.id)
            if expected_rev is not None and current is not None and current.rev != expected_rev:
                raise ConflictError(record.id)
            record = record.model_copy(deep=True)
            check_size(record)
            record.rev = (current.rev if current else 0) + 1
            record.updated = now()
            self._households[record.id] = record
            return record.model_copy(deep=True)

    async def delete(self, household_id: str) -> None:
        async with self._lock:
            self._households.pop(household_id, None)
            for jid in [j.id for j in self._jobs.values() if j.household_id == household_id]:
                self._jobs.pop(jid, None)

    async def list_for(self, uid: str) -> list[HouseholdRecord]:
        return [copy.deepcopy(r) for r in self._households.values() if r.can_read(uid)]

    async def find_demo(self, uid: str, source: str | None = None) -> HouseholdRecord | None:
        for r in self._households.values():
            if r.owner == uid and r.demo and (source is None or r.demo_source == source):
                return r.model_copy(deep=True)
        return None

    async def find_by_share(self, token_hash: str) -> HouseholdRecord | None:
        for r in self._households.values():
            if token_hash in r.share_hashes:
                return r.model_copy(deep=True)
        return None

    async def get_meta(self, key: str) -> dict | None:
        value = self._meta.get(key)
        return copy.deepcopy(value) if value is not None else None

    async def put_meta(self, key: str, value: dict) -> None:
        self._meta[key] = copy.deepcopy(value)

    async def get_job(self, job_id: str) -> Job | None:
        job = self._jobs.get(job_id)
        return job.model_copy(deep=True) if job else None

    async def put_job(self, job: Job) -> Job:
        job = job.model_copy(deep=True)
        job.updated = now()
        self._jobs[job.id] = job
        return job.model_copy(deep=True)
