"""Background jobs with polling.

Firebase Hosting proxies requests to Cloud Run with a 60-second limit, and a
live extraction or AI review can take longer, so slow work runs as a job: the
request returns a job id at once and the browser polls GET /api/jobs/{id}.
On Cloud Run the service is deployed with CPU always allocated so jobs keep
running after the response.
"""

from __future__ import annotations

import asyncio
import logging
import traceback
import uuid
from collections.abc import Awaitable, Callable

from ..store import Job, Store

log = logging.getLogger("jobs")
_running: set[asyncio.Task] = set()

Work = Callable[[Job], Awaitable[dict]]


async def start(store: Store, *, kind: str, household_id: str, owner: str, work: Work) -> Job:
    job = await store.put_job(Job(id=f"job-{uuid.uuid4().hex[:12]}", household_id=household_id, owner=owner, kind=kind))
    task = asyncio.create_task(_run(store, job, work))
    _running.add(task)
    task.add_done_callback(_running.discard)
    return job


async def _run(store: Store, job: Job, work: Work) -> None:
    job.status = "running"
    await store.put_job(job)
    try:
        result = await work(job)
        job.status = "done"
        job.result = result
    except Exception as exc:  # noqa: BLE001 - reported to the user in plain words
        log.error("job %s failed: %s", job.id, traceback.format_exc())
        job.status = "error"
        job.error = str(exc) or type(exc).__name__
    await store.put_job(job)


async def wait_all() -> None:
    """For tests: wait until background jobs finish."""
    while _running:
        await asyncio.gather(*list(_running), return_exceptions=True)
