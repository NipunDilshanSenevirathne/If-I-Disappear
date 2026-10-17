# Implementation status

What the code does today, how each part was checked, and what is still unverified. Plans
and ideas live in [ROADMAP.md](ROADMAP.md); this page is only about
what exists. Last updated: 13 October 2026, version 2.1.0.

**How to read it.** *Tested* means an automated test or the evaluation harness checks it on
every run. *Checked in a browser* means the end-to-end smoke test (`make smoke`, 22 flows) or a
person looked at it. *Tested live* means it was run with a real (free) Gemini key on
13 October 2026, in Chromium with a fake microphone ([LIVE_ACCEPTANCE.md](LIVE_ACCEPTANCE.md)).
*Not verified* means it is built but still needs a real cloud project or a real phone.

## Engine (deterministic)

| Part | Status |
|---|---|
| Household model: people, responsibilities, routes, resources, schedules, windows, lead times | Tested (unit tests, 4 benchmark households) |
| Three-valued readiness for every occurrence of every responsibility across the absence | Tested: 28 of 28 states, 15 of 15 first-problem dates |
| Findings: still needed while away, held by the leaver, clashes, deadlines in and before the absence, not asked, contradictions | Tested: 22 of 22 expected findings, no extras |
| Knockout check that sets false alarms aside, with the reason | Tested: 100% precision and recall on the links that matter (57% for association alone) |
| Repair plan: exhaustive search of fix bundles within a time budget, per-person minutes, what stays open | Tested against the hand-written Perera plan (5 of 5) |
| Explore (what if): someone else away, a thing unavailable, an assumption undone, a different length | Tested (API and a browser flow) |
| Evidence: recording a step done changes state only through the step's typed effects | Tested; checked in a browser |
| Deterministic and order-independent output | Tested: repeated, shuffled, different hash seeds (16 of 16) |

## AI layer

| Part | Status |
|---|---|
| ADK workflows: reading a source, the full check with the reviewer, grading practice | Tested offline (replay); tested live (`make live-check`: every path passed) |
| Free-tier model router: per-model RPM/TPM/RPD ledger, floors, capability matching, fallback, schema validation, cache, per-visitor share | Tested (15 unit tests, simulated days 420/420, 2800/2800, 210/210); tested live: fell through on 503s, a timeout and a used-up daily allowance with nothing failing; cache reused answers |
| Gemma fallback with the schema in the prompt | Tested with a stand-in model; tested live: works but unreliable for extraction (Gemma 4 26B finished 9 of 29 benchmark extractions; 31B answered one short request in 50 s after two "internal error" replies, and timed out on the benchmark) |
| Quote verification (exact after light normalisation) and closest-passage hints | Tested: 947 of 947 misquotes rejected, 295 of 295 harmless differences accepted |
| Redaction of PINs, passwords, codes, card and account numbers; phone numbers to four digits | Tested: 16 of 16, 14 of 14 untouched, 5 of 5 |
| Containment of a hijacked model (extraction, reviewer, grader) | Tested: 19 of 19 |
| Voice notes: recorded in the browser, converted to 16 kHz mono WAV, read by Gemini | Tested live in Chromium (fake microphone): transcribed, facts quoted word for word, a spoken PIN removed; a real phone not verified |
| Spoken practice with Gemini Live (single-use ephemeral tokens) | Tested live in Chromium (fake microphone): the partner set the scene, heard the answer, graded "Explained without help"; first audio after about 1.3 s; a real phone not verified |
| Gemini extraction accuracy on the benchmark sources (`make eval-live`, `make live-models`) | Tested live: quotes word for word 99%, precision 75%, recall 67%, gold findings with no review 6 of 22 ([EVALUATION.md](EVALUATION.md#live-run-13-october-2026)) |

## Web app

| Part | Status |
|---|---|
| Landing page with the live engine result for a sample family, problem facts with sources, finding examples, proof numbers from the report, model lines from the router | Checked in a browser (light, dark, 360–1440 px) |
| Overview: hero with boarding pass, KPI tiles with deltas and sparklines, week-by-week chart with keyboard support, donut, responsibilities, most urgent findings, calendar, readiness trend with the plan's projection | Checked in a browser |
| Live updates: a small "has anything changed?" call every 6 s refreshes every chart; the AI meter refreshes every 10 s | Checked in a browser |
| What we found, Explore, Calendar, Plan (with evidence), Practise (typed), Card (print), Share and the handover page | Checked in a browser (smoke test) |
| Capture: talk, photo or PDF (drag and drop), type, by hand; sample documents; consent; progress with the model per step; sources with highlights | Checked in a browser offline and tested live (photo, voice note) |
| Review facts: collapsible per source, accept, reject, dispute, undo, edit a value or date, accept all checked | Checked in a browser |
| Household settings: dates, absence kind, people, scope switches, add by hand, AI allowance, theme, tour, export, delete | Checked in a browser |
| How it was worked out: the flow (AI reads, code decides), steps with models, time split | Checked in a browser |
| Evaluation page rendering the harness report | Checked in a browser |
| Quick tour (12 steps, spotlight, keyboard, phone layout) | Checked in a browser |
| Light, dark and system themes, no flash on load | Checked in a browser |
| Accessibility: labels, focus, reduced motion, colour plus icon plus word for every state | axe-core (WCAG 2.2 A and AA) on all 16 screens in light and dark, desktop and phone: 64 of 64 with no violations (`make a11y`, in CI); Lighthouse accessibility 100 on the pages measured; a screen-reader pass on real devices is still to do |
| Phone layout (no sideways scrolling at 360 px, bottom bar) | Checked in Chromium's phone emulation; real devices still to do |
| Speed on a phone: text compressed with gzip, each screen loaded on demand, the Live and Firebase SDKs only when used | Lighthouse (`make lighthouse`): performance 90–94 on the phone profile, 97–100 on desktop; 100 for accessibility, best practices and SEO |

## Cloud and operations

| Part | Status |
|---|---|
| Single container (web + API) for Cloud Run | Built and smoke-tested in CI (`docker build`, health, demo, browser flows) |
| `infra/setup.sh` and `infra/deploy.sh` (APIs, Artifact Registry, Firestore, private bucket, service account, secrets, deploy) | Written and syntax-checked; a fresh-project run is in the live checklist |
| Firestore store, Cloud Storage uploads, the ledger saved across restarts | Built; the memory store is what the tests use |
| Visitor sessions (signed), Firebase Auth option | Session mode tested; Firebase option not verified |

## Known gaps

- Live Gemini was tested for one day on one free key; real phones, Cloud Run with Firestore and real households are still to come ([LIVE_ACCEPTANCE.md](LIVE_ACCEPTANCE.md)).
- Extraction recall is about two thirds, and Gemma is a weak last resort; people review every fact.
- Free-tier limits change; they are settings (`QUOTA_LIMITS`).
- The benchmark households are synthetic. No real families have used it yet.
- One Cloud Run instance is recommended on the free tier, so the ledger stays exact.
