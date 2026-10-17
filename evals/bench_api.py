"""Response times of the running API, end to end over HTTP.

    python -m evals.bench_api [base_url]        (default http://localhost:8080)

Measures the endpoints a visitor actually waits for: opening a sample household, the live
"has anything changed?" poll, what-if questions, re-planning, the card, the full check with
the AI reviewer, reading a sample document and grading a typed explanation. Then a burst of
parallel visitors. Writes evals/reports/api-benchmark.md and .json.

Run it against a server in the mode you want to describe. In offline mode (AI_MODE=fixture)
the AI steps replay reviewed answers through the same ADK workflows, so the numbers are the
app's own overhead: they do not include Google's model latency. Each visitor in the
benchmark is a separate user (AUTH_MODE=dev, the X-Dev-User header), so per-user rate limits
are not hit; it does not work against a deployment in session mode.
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")
OUT = Path(__file__).parent / "reports"
RUN = f"bench{int(time.time())}"


def user(n: int | str) -> dict[str, str]:
    return {"X-Dev-User": f"{RUN}-{n}"}


def pct(values: list[float], p: float) -> float:
    s = sorted(values)
    if not s:
        return float("nan")
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def summary(name: str, what: str, times: list[float]) -> dict:
    return {
        "name": name,
        "what": what,
        "n": len(times),
        "median_ms": round(statistics.median(times), 1),
        "p95_ms": round(pct(times, 0.95), 1),
        "max_ms": round(max(times), 1),
    }


async def timed(client: httpx.AsyncClient, method: str, url: str, **kw) -> tuple[float, httpx.Response]:
    t = time.perf_counter()
    r = await client.request(method, BASE + url, **kw)
    ms = (time.perf_counter() - t) * 1000
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {url} -> {r.status_code}: {r.text[:300]}")
    return ms, r


async def wait_job(client: httpx.AsyncClient, job: dict, headers: dict) -> dict:
    """Poll a job like the browser does (but every 50 ms) until it finishes."""
    while job.get("status") not in ("done", "error"):
        await asyncio.sleep(0.05)
        r = await client.get(f"{BASE}/api/jobs/{job['id']}", headers=headers)
        r.raise_for_status()
        job = r.json()
    if job["status"] == "error":
        raise RuntimeError(f"job failed: {job.get('error')}")
    return job


async def main() -> None:
    results: list[dict] = []
    async with httpx.AsyncClient(timeout=120) as c:
        health = (await c.get(f"{BASE}/api/health")).json()

        # warm up (first import of some modules, first request through the stack)
        await c.post(f"{BASE}/api/demo", json={}, headers=user("warm"))

        times = [(await timed(c, "GET", "/api/health"))[0] for _ in range(60)]
        results.append(summary("GET /api/health", "liveness", times))

        # a fresh private copy of the sample household for each visitor
        homes: list[tuple[dict, str]] = []
        times = []
        for i in range(12):
            h = user(i)
            ms, r = await timed(c, "POST", "/api/demo", json={}, headers=h)
            times.append(ms)
            homes.append((h, r.json()["id"]))
        results.append(
            summary(
                "POST /api/demo",
                "open the sample: copy the household and compute everything",
                times,
            )
        )

        h, hid = homes[0]
        times = [(await timed(c, "GET", f"/api/households/{hid}", headers=h))[0] for _ in range(40)]
        results.append(
            summary(
                "GET /api/households/{id}",
                "the whole household view the dashboard renders",
                times,
            )
        )

        times = [(await timed(c, "GET", f"/api/households/{hid}/pulse", headers=h))[0] for _ in range(80)]
        results.append(summary("GET …/pulse", "the live poll every open screen makes every 6 s", times))

        times = [(await timed(c, "GET", "/api/ai/usage", headers=h))[0] for _ in range(40)]
        results.append(summary("GET /api/ai/usage", "the live AI allowance meter", times))

        bodies = [
            {"also_away": ["sunil"]},
            {"unavailable": ["nirmala_phone"]},
            {"days": 180},
            {"also_away": ["kamala"], "unavailable": ["clinic_book"]},
        ]
        times = []
        for i in range(40):
            ms, _ = await timed(
                c,
                "POST",
                f"/api/households/{hid}/explore",
                json=bodies[i % len(bodies)],
                headers=h,
            )
            times.append(ms)
        results.append(
            summary(
                "POST …/explore",
                "a what-if: re-simulate a changed copy of the absence",
                times,
            )
        )

        times = []
        for i in range(30):
            ms, _ = await timed(
                c,
                "POST",
                f"/api/households/{hid}/plan",
                json={"budget_minutes": [30, 60, 90, 120][i % 4]},
                headers=h,
            )
            times.append(ms)
        results.append(
            summary(
                "POST …/plan",
                "re-plan for another time budget (exhaustive search)",
                times,
            )
        )

        times = [(await timed(c, "GET", f"/api/households/{hid}/card", headers=h))[0] for _ in range(30)]
        results.append(summary("GET …/card", "the Continuity Card", times))

        # the full check: ADK analysis workflow with the reviewer (replayed offline)
        times = []
        for i in range(8):
            hh, hhid = homes[1 + i]
            t = time.perf_counter()
            r = await c.post(f"{BASE}/api/households/{hhid}/analyze", json={}, headers=hh)
            r.raise_for_status()
            await wait_job(c, r.json()["job"], hh)
            times.append((time.perf_counter() - t) * 1000)
        results.append(
            summary(
                "POST …/analyze → job",
                "the full check with the AI reviewer, start to finished job",
                times,
            )
        )

        # reading a sample document: upload, ADK ingest workflow, quote checks, save
        samples = (await c.get(f"{BASE}/api/samples")).json()
        sample = next(s for s in samples if s["kind"] == "image")
        blob = (await c.get(BASE + sample["url"])).content
        times = []
        for i in range(8):
            hh, hhid = homes[1 + i]
            files = {"file": (sample["url"].split("/")[-1], blob, sample["mime_type"])}
            t = time.perf_counter()
            r = await c.post(
                f"{BASE}/api/households/{hhid}/sources",
                data={"title": sample["title"], "consent": "true"},
                files=files,
                headers=hh,
            )
            r.raise_for_status()
            await wait_job(c, r.json()["job"], hh)
            times.append((time.perf_counter() - t) * 1000)
        results.append(
            summary(
                "POST …/sources → job",
                f"read a sample photo ({len(blob) // 1024} KB) into checked facts",
                times,
            )
        )

        attempt = {
            "person": "sunil",
            "transcript": "The paper bill comes every month and I pay it by the 10th. I take the bill and the cash "
            "to the post office, and I keep the receipt with the bill.",
            "hints_given": 0,
            "mode": "text",
        }
        times = []
        for i in range(10):
            hh, hhid = homes[i % len(homes)]
            ms, _ = await timed(
                c,
                "POST",
                f"/api/households/{hhid}/practice/r_electricity/attempts",
                json=attempt,
                headers=hh,
            )
            times.append(ms)
        results.append(
            summary(
                "POST …/practice/…/attempts",
                "grade a typed explanation and recompute readiness",
                times,
            )
        )

        # a burst: many visitors at once on one process
        async def burst(n_requests: int, concurrency: int, make) -> dict:
            sem = asyncio.Semaphore(concurrency)
            lat: list[float] = []

            async def one(i: int) -> None:
                async with sem:
                    method, url, kw = make(i)
                    ms, _ = await timed(c, method, url, **kw)
                    lat.append(ms)

            t = time.perf_counter()
            await asyncio.gather(*(one(i) for i in range(n_requests)))
            wall = time.perf_counter() - t
            return {
                "requests": n_requests,
                "concurrency": concurrency,
                "throughput_per_s": round(n_requests / wall, 1),
                "median_ms": round(statistics.median(lat), 1),
                "p95_ms": round(pct(lat, 0.95), 1),
                "errors": 0,
            }

        def pulse(i: int):
            hh, hhid = homes[i % len(homes)]
            return "GET", f"/api/households/{hhid}/pulse", {"headers": hh}

        def what_if(i: int):
            hh, hhid = homes[i % len(homes)]
            return (
                "POST",
                f"/api/households/{hhid}/explore",
                {"json": bodies[i % len(bodies)], "headers": hh},
            )

        bursts = {
            "pulse": await burst(600, 50, pulse),
            "explore": await burst(120, 12, what_if),
        }

    report = {
        "generated": datetime.now(UTC).isoformat(timespec="seconds"),
        "base": BASE,
        "server": {
            "version": health.get("version"),
            "ai": health.get("ai_mode"),
            "store": health.get("store"),
        },
        "machine": {
            "python": platform.python_version(),
            "cpus": os.cpu_count(),
            "platform": platform.platform(terse=True),
        },
        "endpoints": results,
        "bursts": bursts,
    }
    OUT.mkdir(exist_ok=True)
    (OUT / "api-benchmark.json").write_text(json.dumps(report, indent=2) + "\n")
    (OUT / "api-benchmark.md").write_text(render(report))
    print(render(report))


def render(rep: dict) -> str:
    srv = rep["server"]
    lines = [
        "# API response times",
        "",
        f"Generated {rep['generated']} by `python -m evals.bench_api` against {rep['base']} "
        f"(server {srv.get('version')}, AI: {srv.get('ai')}, store: {srv.get('store')}). "
        f"Client and server on the same machine: {rep['machine']['cpus']} vCPUs, Python {rep['machine']['python']}, "
        "one server process.",
        "",
        "Times are end to end over HTTP, as a browser on the same network would see them. In offline mode the AI "
        "steps replay reviewed answers through the same ADK workflows, so these are the app's own costs; with a key, "
        "add Google's model time to the two jobs. On Cloud Run, Firestore adds a few milliseconds per read and write.",
        "",
        "| Endpoint | What it does | Runs | Median | 95th percentile | Slowest |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in rep["endpoints"]:
        lines.append(f"| `{r['name']}` | {r['what']} | {r['n']} | {r['median_ms']} ms | {r['p95_ms']} ms | {r['max_ms']} ms |")
    lines += [
        "",
        "## Many visitors at once (one process)",
        "",
        "| Burst | Requests | In parallel | Throughput | Median | 95th percentile | Errors |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    names = {
        "pulse": "Live polls (`…/pulse`)",
        "explore": "What-if questions (`…/explore`)",
    }
    for k, b in rep["bursts"].items():
        lines.append(
            f"| {names.get(k, k)} | {b['requests']} | {b['concurrency']} | {b['throughput_per_s']} /s | "
            f"{b['median_ms']} ms | {b['p95_ms']} ms | {b['errors']} |"
        )
    lines += [
        "",
        "This file is generated. Run `python -m evals.bench_api` again (with the API running) to refresh it.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    asyncio.run(main())
