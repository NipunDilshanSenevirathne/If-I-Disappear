"""Firestore store for deployment.

Layout
  households/{householdId}            HouseholdRecord (owner, members, data, analysis, log, shares, history, rev)
  jobs/{jobId}                        Job
  meta/{key}                          small server state (today's free-tier usage)
Clients never read Firestore directly: security rules deny all client access and
the API (Admin credentials on Cloud Run) checks ownership on every request.
"""

from __future__ import annotations

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from .base import ConflictError, HouseholdRecord, Job, check_size, now


class FirestoreStore:
    def __init__(self, project: str | None = None) -> None:
        self.db = firestore.AsyncClient(project=project)
        self.households = self.db.collection("households")
        self.jobs = self.db.collection("jobs")
        self.meta = self.db.collection("meta")

    async def get(self, household_id: str) -> HouseholdRecord | None:
        snap = await self.households.document(household_id).get()
        return HouseholdRecord.model_validate(snap.to_dict()) if snap.exists else None

    async def put(self, record: HouseholdRecord, *, expected_rev: int | None = None) -> HouseholdRecord:
        ref = self.households.document(record.id)
        transaction = self.db.transaction()

        @firestore.async_transactional
        async def write(tx):
            snap = await ref.get(transaction=tx)
            current_rev = snap.to_dict().get("rev", 0) if snap.exists else 0
            if expected_rev is not None and snap.exists and current_rev != expected_rev:
                raise ConflictError(record.id)
            data = record.model_copy(deep=True)
            check_size(data)
            data.rev = current_rev + 1
            data.updated = now()
            tx.set(ref, data.model_dump(mode="json"))
            return data

        return await write(transaction)

    async def delete(self, household_id: str) -> None:
        await self.households.document(household_id).delete()
        async for doc in self.jobs.where(filter=FieldFilter("household_id", "==", household_id)).stream():
            await doc.reference.delete()

    async def list_for(self, uid: str) -> list[HouseholdRecord]:
        out: dict[str, HouseholdRecord] = {}
        async for doc in self.households.where(filter=FieldFilter("owner", "==", uid)).stream():
            out[doc.id] = HouseholdRecord.model_validate(doc.to_dict())
        async for doc in self.households.where(filter=FieldFilter("members", "array_contains", uid)).stream():
            out[doc.id] = HouseholdRecord.model_validate(doc.to_dict())
        return list(out.values())

    async def find_demo(self, uid: str, source: str | None = None) -> HouseholdRecord | None:
        # equality filters only, so no composite index is needed
        query = self.households.where(filter=FieldFilter("owner", "==", uid)).where(filter=FieldFilter("demo", "==", True))
        if source is not None:
            query = query.where(filter=FieldFilter("demo_source", "==", source))
        query = query.limit(1)
        async for doc in query.stream():
            return HouseholdRecord.model_validate(doc.to_dict())
        return None

    async def find_by_share(self, token_hash: str) -> HouseholdRecord | None:
        query = self.households.where(filter=FieldFilter("share_hashes", "array_contains", token_hash)).limit(1)
        async for doc in query.stream():
            return HouseholdRecord.model_validate(doc.to_dict())
        return None

    async def get_meta(self, key: str) -> dict | None:
        snap = await self.meta.document(key).get()
        return snap.to_dict() if snap.exists else None

    async def put_meta(self, key: str, value: dict) -> None:
        await self.meta.document(key).set(value)

    async def get_job(self, job_id: str) -> Job | None:
        snap = await self.jobs.document(job_id).get()
        return Job.model_validate(snap.to_dict()) if snap.exists else None

    async def put_job(self, job: Job) -> Job:
        job = job.model_copy(deep=True)
        job.updated = now()
        await self.jobs.document(job.id).set(job.model_dump(mode="json"))
        return job
