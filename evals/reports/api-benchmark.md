# API response times

Generated 2026-10-13T09:18:43+00:00 by `python -m evals.bench_api` against http://localhost:8080 (server 2.1.0, AI: fixture, store: memory). Client and server on the same machine: 2 vCPUs, Python 3.13.16, one server process.

Times are end to end over HTTP, as a browser on the same network would see them. In offline mode the AI steps replay reviewed answers through the same ADK workflows, so these are the app's own costs; with a key, add Google's model time to the two jobs. On Cloud Run, Firestore adds a few milliseconds per read and write.

| Endpoint | What it does | Runs | Median | 95th percentile | Slowest |
|---|---|---:|---:|---:|---:|
| `GET /api/health` | liveness | 60 | 1.9 ms | 2.1 ms | 3.4 ms |
| `POST /api/demo` | open the sample: copy the household and compute everything | 12 | 475.1 ms | 559.8 ms | 564.3 ms |
| `GET /api/households/{id}` | the whole household view the dashboard renders | 40 | 42.4 ms | 54.3 ms | 146.1 ms |
| `GET …/pulse` | the live poll every open screen makes every 6 s | 80 | 6.3 ms | 8.9 ms | 11.1 ms |
| `GET /api/ai/usage` | the live AI allowance meter | 40 | 2.3 ms | 3.3 ms | 5.3 ms |
| `POST …/explore` | a what-if: re-simulate a changed copy of the absence | 40 | 11.6 ms | 14.7 ms | 15.5 ms |
| `POST …/plan` | re-plan for another time budget (exhaustive search) | 30 | 140.9 ms | 208.3 ms | 300.6 ms |
| `GET …/card` | the Continuity Card | 30 | 10.3 ms | 14.1 ms | 15.2 ms |
| `POST …/analyze → job` | the full check with the AI reviewer, start to finished job | 8 | 228.9 ms | 319.0 ms | 346.8 ms |
| `POST …/sources → job` | read a sample photo (379 KB) into checked facts | 8 | 99.6 ms | 153.8 ms | 179.1 ms |
| `POST …/practice/…/attempts` | grade a typed explanation and recompute readiness | 10 | 226.3 ms | 347.0 ms | 419.7 ms |

## Many visitors at once (one process)

| Burst | Requests | In parallel | Throughput | Median | 95th percentile | Errors |
|---|---:|---:|---:|---:|---:|---:|
| Live polls (`…/pulse`) | 600 | 50 | 162.7 /s | 285.6 ms | 443.8 ms | 0 |
| What-if questions (`…/explore`) | 120 | 12 | 82.0 /s | 144.9 ms | 292.1 ms | 0 |

This file is generated. Run `python -m evals.bench_api` again (with the API running) to refresh it.
