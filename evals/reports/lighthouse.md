# Lighthouse

Generated 2026-10-13T12:29:48+00:00 by `python -m evals.lighthouse_report` with Lighthouse 12.8.2, against http://localhost:8080. Phone runs use Lighthouse's default emulation (a mid-range phone on slow 4G with a 4× slower CPU, simulated); desktop runs use its desktop preset. Scores are out of 100.

| Page | Form | Performance | Accessibility | Best practices | SEO | First paint | Largest paint | Blocking time | Layout shift | Downloaded |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Landing | mobile | **93** | 100 | 100 | 100 | 1.8 s | 2.4 s | 213 ms | 0.012 | 231 KiB |
| Landing | desktop | **100** | 100 | 100 | 100 | 0.4 s | 0.5 s | 0 ms | 0.02 | 231 KiB |
| Household overview (sample family) | mobile | **90** | 100 | 100 | 100 | 1.8 s | 3.0 s | 187 ms | 0.042 | 275 KiB |
| Household overview (sample family) | desktop | **97** | 100 | 100 | 100 | 0.4 s | 0.7 s | 17 ms | 0.079 | 275 KiB |
| Evaluation report | mobile | **94** | 100 | 100 | 100 | 1.9 s | 2.7 s | 120 ms | 0.035 | 236 KiB |
| Evaluation report | desktop | **100** | 100 | 100 | 100 | 0.5 s | 0.6 s | 0 ms | 0.018 | 236 KiB |
| Start your own household | mobile | **94** | 100 | 100 | 100 | 1.9 s | 2.7 s | 109 ms | 0.01 | 230 KiB |
| Start your own household | desktop | **100** | 100 | 100 | 100 | 0.5 s | 0.6 s | 0 ms | 0.009 | 230 KiB |

A deployed Cloud Run service adds the network between the phone and Google's edge, and a cold start adds a few seconds to the first visit (none with `MIN_INSTANCES=1`).

This fileis generated. Run `make lighthouse` (with the app running) to refresh it.
