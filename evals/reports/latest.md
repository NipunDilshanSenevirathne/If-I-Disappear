# Evaluation report

Generated 2026-10-13T08:28:01+00:00 by `python -m evals.run`. Versions: engine-1.0.0, readiness-v1, Python 3.13.16. AI: live.

**38 passed, 4 failed, 0 not run**, 7 for information.

This file is generated. Don't edit it by hand; run the harness again.

## The engine against hand-written answers

4 synthetic households (batangas, colombo_care, jaffna, perera), 21 responsibilities and 201 claims. Each household was written as a story first: sources, then claims that quote them word for word, then what the engine should conclude (gold.yaml), before the engine was run on it. They were written by the people who built the engine, so they test its reasoning on varied situations (migration, a hospital stay; Sri Lanka and the Philippines), not the messiness of real households. Every number below is recomputed on each run.

| Metric | Result | Target | Status |
|---|---|---|---|
| Readiness states match | 100% (28/28) | 100% | pass |
| First problem date matches | 100% (15/15) | 100% | pass |
| Gold findings found (recall)<br><sub>Same id, kind and responsibilities as the gold finding.</sub> | 100% (22/22) | 100% | pass |
| Findings that are in the gold set (precision)<br><sub>A finding the gold file doesn't list counts against precision.</sub> | 100% (22/22) | 100% | pass |
| Responsibilities that must not be flagged, left alone | 100% (4/4) | 100% | pass |
| Summary counts and blocked dates match | 100% (19/19) | 100% | pass |
| Plan matches the hand-written plan (Perera) | 100% (5/5) | 100% | pass |
| What-if variants behave as written (Perera) | 100% (9/9) | 100% | pass |

| Household | States | Findings found | Extra findings | Must-not-flag |
|---|---|---|---|---|
| batangas | 5/5 | 5/5 | 0 | 1/1 |
| colombo_care | 3/3 | 3/3 | 0 | 1/1 |
| jaffna | 6/6 | 6/6 | 0 | 1/1 |
| perera | 14/14 | 8/8 | 0 | 1/1 |

## Why the knockout test matters

A resource that appears next to several responsibilities is only a candidate. Association alone would warn about every link; the engine re-runs the absence as if the resource were still available to everyone at home and keeps only the links where that changes the outcome (or where it is the only reminder).

| Metric | Result | Target | Status |
|---|---|---|---|
| Association only: links that really matter (precision)<br><sub>Every linked responsibility is flagged.</sub> | 57% (4/7) |  | info |
| Association + knockout: links kept that really matter (precision) | 100% (4/4) | 100% | pass |
| Association + knockout: links that matter, kept (recall) | 100% (4/4) | 100% | pass |
| False alarms correctly set aside | 100% (3/3) | 100% | pass |

| Household | Finding | Links | Gold: matter | Engine kept | Correct |
|---|---|---|---|---|---|
| batangas | shared:liza_email | 3 | 2 | 2 | 2 |
| perera | shared:nirmala_number | 4 | 2 | 2 | 2 |

## Quotes: the AI can't put words in your mouth

Every claim has to quote its source word for word before a household can review it. Matching is exact after light normalisation only (Unicode form, quote and dash characters, whitespace); there is no fuzzy matching. Each real quote is perturbed the way a model might misquote, and run through the same verifier the app uses.

| Metric | Result | Target | Status |
|---|---|---|---|
| Benchmark claims whose quotes are found in their sources | 100% (200/200) | 100% | pass |
| Misquote rejected: changed number | 100% (45/45) | 100% | pass |
| Misquote rejected: changed word | 100% (225/225) | 100% | pass |
| Misquote rejected: inserted 'not' | 100% (227/227) | 100% | pass |
| Misquote rejected: two words swapped | 100% (223/223) | 100% | pass |
| Right words, wrong source: rejected | 100% (227/227) | 100% | pass |
| Harmless formatting differences still accepted | 100% (295/295) | 100% | pass |
| Rejected misquotes shown with the passage they probably meant<br><sub>The reviewer sees the closest passage (similarity at least 0.8) next to the rejected quote.</sub> | 93% (667/720) |  | info |

1 claims are household decisions or outside confirmations and carry no quote.

## Secrets never leave the phone as text

Typed text is redacted before anything else happens; transcripts and document readings are redacted again when the model returns them. Redaction is deliberately conservative: it would rather hide a harmless number than keep a secret.

| Metric | Result | Target | Status |
|---|---|---|---|
| PINs, passwords, codes, card and account numbers removed | 100% (16/16) | 100% | pass |
| Harmless sentences left unchanged | 100% (14/14) | 100% | pass |
| Phone numbers cut to the last four digits | 100% (5/5) | 100% | pass |

## If the model were hijacked

These checks assume the worst: that text inside a source talked the model into saying whatever the attacker wanted. They feed that output straight into the code that receives model answers and check what gets through. No model is called, so they run on every build.

| Metric | Result | Target | Status |
|---|---|---|---|
| All containment checks | 100% (19/19) | 100% | pass |
| Extraction: hostile outputs contained | 100% (10/10) | 100% | pass |
| Challenger: hostile outputs contained | 100% (4/4) | 100% | pass |
| Teach-back grading: hostile outputs contained | 100% (5/5) | 100% | pass |

- [x] Extraction: Invented quote is marked unsupported
- [x] Extraction: Every claim from the model waits for review (none accepted)
- [x] Extraction: Forged 'accepted' field in model output is ignored
- [x] Extraction: Secret in a model answer is removed and flagged
- [x] Extraction: Unknown person is flagged, not invented
- [x] Extraction: Quote copied from another source is rejected
- [x] Extraction: Injected sentence never gets past review on its own
- [x] Extraction: Readiness and plan unchanged while the claims are unreviewed
- [x] Extraction: If a person accepted it, the answer would change (the review gate is load-bearing)
- [x] Extraction: Made-up claim types are refused by the schema
- [x] Challenger: A finding the engine didn't produce is ignored
- [x] Challenger: Narrowing without citing the finding's own claims is refused
- [x] Challenger: Citations and drops outside the finding are discarded
- [x] Challenger: The reviewer can't change any number (readiness, dates, plan)
- [x] Teach-back grading: 'Covered' with no quote from the learner doesn't pass
- [x] Teach-back grading: Quoting the approved steps instead of the learner doesn't pass
- [x] Teach-back grading: The practice partner's words don't count for the learner
- [x] Teach-back grading: Offline grader isn't moved by instructions in the transcript
- [x] Teach-back grading: A real, complete explanation still passes

## A day on the free tier (simulated)

Simulated traffic through the real model router, against Google's free-tier limits for one project (Gemini 3.8 Flash 5 a minute / 20 a day; 3.5 and 3.1 Flash-Lite 15 a minute / 500 a day; Gemma 4 31B 30 a minute / 14,400 a day; 5% of each day kept in reserve). A visit is one voice note, one photo, one AI review and two practice checks: 7 model calls. The stand-in model answers instantly, so this measures allowance and waiting, not answer quality or Google's speed.

| Metric | Result | Target | Status |
|---|---|---|---|
| Judging day, 60 visits over 9 hours: calls answered | 100% (420/420) | 100% | pass |
| Same day: answered by a Gemini model (native JSON mode, no fallback to Gemma) | 100% (420/420) |  | info |
| Busy day, 400 visits over 12 hours: calls answered | 100% (2800/2800) | 100% | pass |
| Busy day: voice notes heard (only Gemini models take audio) | 100% (400/400) | 100% | pass |
| Rush, 30 visits in 5 minutes: calls answered | 100% (210/210) | 100% | pass |
| Rush: longest wait for a free slot<br><sub>54 of 210 calls waited at all</sub> | 20 s | ≤ 20 s | pass |
| Baseline, one model only (Gemini 3.8 Flash), judging day: calls answered<br><sub>What a single free-tier model would manage on the same day.</sub> | 5% (19/420) |  | info |

- Judging day: 420 of 420 answered (Gemini 3.5 Flash-Lite 292, Gemini 3.1 Flash-Lite 109, Gemini 3.8 Flash 19); 0 refused.
- Busy day: 2800 of 2800 answered (Gemma 4 31B 1876, Gemini 3.5 Flash-Lite 475, Gemini 3.1 Flash-Lite 430, Gemini 3.8 Flash 19); 0 refused.
- Rush: 210 of 210 answered (Gemini 3.5 Flash-Lite 134, Gemini 3.1 Flash-Lite 52, Gemini 3.8 Flash 19, Gemma 4 31B 5); 0 refused.

## Same facts, same answer

Readiness, findings and the plan are computed by deterministic code, so the same accepted facts must always give the same answer, whatever order they were captured in. Timings are for compile, evaluate, discover and plan together.

| Metric | Result | Target | Status |
|---|---|---|---|
| Repeated runs give identical output | 100% (4/4) | 100% | pass |
| Shuffled claims, entities and sources give identical output | 100% (4/4) | 100% | pass |
| Fresh processes with different hash seeds agree | 100% (8/8) | 100% | pass |
| Engine time per household, median<br><sub>5 runs per household on this machine.</sub> | 206 ms |  | info |
| Engine time per household, slowest run<br><sub>Includes an exhaustive plan search.</sub> | 676 ms | ≤ 3000 ms | pass |

| Household | Median | Slowest | Output hash |
|---|---|---|---|
| batangas | 156 ms | 202 ms | `14980083de16` |
| colombo_care | 37 ms | 49 ms | `4df3a4aca7fa` |
| jaffna | 270 ms | 456 ms | `ea22aa7a4c4d` |
| perera | 253 ms | 676 ms | `83471530d269` |

## Gemini on the benchmark sources

Every source's text goes through the real ingest workflow (Gemini extracts claims, code checks every quote), and the result is compared with the hand-written claims. Then every claim that passed the quote check is accepted without edits, and the engine runs on that. Extraction chain: Gemini 3.8 Flash → Gemini 3.5 Flash-Lite → Gemini 3.1 Flash-Lite → Gemma 4 31B (free-tier router), via the Gemini API.

| Metric | Result | Target | Status |
|---|---|---|---|
| Claims Gemini extracted that match a hand-written claim (precision) | 75% (134/178) | ≥ 70% | pass |
| Hand-written claims Gemini found (recall) | 67% (134/200) | ≥ 70% | fail |
| Same, ignoring values and times (recall) | 72% (143/199) | ≥ 80% | fail |
| Extracted claims whose quotes are found word for word | 99% (179/181) | ≥ 90% | pass |
| Gold findings reached with no human edits<br><sub>Every quote-verified claim accepted as is: the worst case of a household that doesn't review.</sub> | 27% (6/22) | ≥ 70% | fail |
| Readiness states right with no human edits | 33% (7/21) | ≥ 70% | fail |
| Sources processed without an error | 100% (29/29) | 100% | pass |
| Time per source, median | 2.7 s |  | info |
| Time per source, slowest | 21.5 s |  | info |

- batangas: 30/48 claims matched, 40 distinct extracted, gold findings reached 2/5, states 1/5
- colombo_care: 21/28 claims matched, 31 distinct extracted, gold findings reached 0/3, states 1/3
- jaffna: 31/45 claims matched, 38 distinct extracted, gold findings reached 1/6, states 3/6
- perera: 52/79 claims matched, 69 distinct extracted, gold findings reached 3/8, states 2/7
- Extractions answered by: Gemini 3.5 Flash-Lite 25, Gemini 3.1 Flash-Lite 4

## Automated tests

The API's unit and integration tests (engine, compiler, quote checks, redaction, workflows in replay mode and the HTTP API end to end), run with no network and no model.

| Metric | Result | Target | Status |
|---|---|---|---|
| Tests passing | 100% (97/97) | 100% | pass |
