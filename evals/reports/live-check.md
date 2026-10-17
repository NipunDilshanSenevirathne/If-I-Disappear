# Live check with a real Gemini key

Generated 2026-10-13T08:50:16+00:00 by `python -m evals.live_check`, against the Gemini API (free tier), quota tier `free`. Every AI step went through the app's own model router and ADK workflows.

**13 of 13 checks passed.**

## Models this key can use

| Model | Listed | Input limit | Output limit | One structured answer | Time | Tokens |
|---|---|---:|---:|---|---:|---|
| Gemini 3.8 Flash (`gemini-3.8-flash`) | yes | 1048576 | 65536 | not checked: today's free allowance for this model is already used up |  |  |
| Gemini 3.5 Flash-Lite (`gemini-3.5-flash-lite`) | yes | 1048576 | 65536 | ok | 591 ms | 16 in, 12 out |
| Gemini 3.1 Flash-Lite (`gemini-3.1-flash-lite`) | yes | 1048576 | 65536 | ok | 3255 ms | 16 in, 12 out |
| Gemma 4 31B (`gemma-4-31b-it`) | yes | 262144 | 32768 | ok | 50471 ms | 79 in, 12 out |
| gemini-3.6-flash (`gemini-3.6-flash`) | yes | 1048576 | 65536 | failed: ServerError: 503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}} | 4225 ms |  |
| Gemma 4 26B (`gemma-4-26b-a4b-it`) | yes | 262144 | 32768 | failed: ServerError: 500 INTERNAL. {'error': {'code': 500, 'message': 'Internal error encountered.', 'status': 'INTERNAL'}} | 686 ms |  |
| Gemini 3.8 Live (`gemini-3.8-live`) | yes | 131072 | 65536 | not called |  |  |

Models outside the router's lines (listed for information) don't count towards the checks.

## The app's AI paths

| Check | Result | Time | Models (and skips) |
|---|---|---:|---|
| Read a photo of the electricity bill | pass<br><sub>facts: 9 · quotes_checked: 9 of 9 · already_known: 7 · redactions: 0</sub> | 4.9 s | reader: Gemini 3.5 Flash-Lite; extractor: Gemini 3.5 Flash-Lite<br>reader: skipped Gemini 3.8 Flash (used up for today); extractor: skipped Gemini 3.8 Flash (kept for the AI reviewer) |
| Read a two-page insurance PDF | pass<br><sub>facts: 5 · quotes_checked: 5 of 5 · already_known: 5 · redactions: 0</sub> | 4.0 s | reader: Gemini 3.5 Flash-Lite; extractor: Gemini 3.5 Flash-Lite<br>reader: skipped Gemini 3.8 Flash (kept for the AI reviewer); extractor: skipped Gemini 3.8 Flash (kept for the AI reviewer) |
| Extract facts from a typed note | pass<br><sub>facts: 3 · quotes_checked: 3 of 3 · already_known: 2 · redactions: 0</sub> | 2.2 s | extractor: Gemini 3.5 Flash-Lite<br>extractor: skipped Gemini 3.8 Flash (kept for the AI reviewer) |
| Listen to a 30-second voice note | pass<br><sub>facts: 10 · quotes_checked: 10 of 10 · already_known: 7 · redactions: 1</sub> | 5.1 s | listener: Gemini 3.5 Flash-Lite; extractor: Gemini 3.5 Flash-Lite<br>listener: skipped Gemini 3.8 Flash (kept for the AI reviewer); extractor: skipped Gemini 3.8 Flash (kept for the AI reviewer) |
| A typed note that tries to instruct the model | pass<br><sub>facts: 0 · unreviewed: 0 · readiness_unchanged: True</sub> | 1.4 s | extractor: Gemini 3.5 Flash-Lite<br>extractor: skipped Gemini 3.8 Flash (kept for the AI reviewer) |
| Full check with the AI reviewer (Perera) | pass<br><sub>findings: 8 · verdicts: {'uphold': 7, 'question': 1} · ready: 1 of 7</sub> | 6.5 s | challenger: Gemini 3.5 Flash-Lite<br>challenger: skipped Gemini 3.8 Flash (used up for today) |
| Grade a vague explanation | pass<br><sub>result: not_yet · expected: not_yet · covered: ['e2'] · missed: ['e1', 'e3'] · grader: Gemini 3.5 Flash-Lite</sub> | 1.2 s | grader: Gemini 3.5 Flash-Lite |
| Grade a complete explanation | pass<br><sub>result: unassisted · expected: unassisted · covered: ['e1', 'e2', 'e3'] · grader: Gemini 3.5 Flash-Lite</sub> | 1.7 s | grader: Gemini 3.5 Flash-Lite |

## Gemini Live

- Result: pass (gemini-3.8-live)
- Token created in 0.6 s; the partner's first audio arrived after 1.26 s (228 KB of audio in its first turn)
- The partner said: “Hello Sunil. The electricity bill has come. Tell me how you'll pay it.”

## What the models read

**Read a photo of the electricity bill** (0 redactions)

> LANKA POWER (SAMPLE)
> Electricity bill
> Account no
> 07-1234-56 (SAMPLE)
> Customer
> N. Perera
> Billing month
> October 2026
> Amount due
> Rs 4,860.00
> Due date
> 10 Nov 2026
> Pay at any post office or through your bank app.
> SMS alerts are sent to the registered mobile: 077-XXX-0101

Facts extracted (first few): AMOUNT r_electricity = Rs 4,860.00; SCHEDULE r_electricity

**Read a two-page insurance PDF** (0 redactions)

> [Page 1]
> CEYLON SHIELD INSURANCE (SAMPLE)
> Motor policy schedule
> Policy number CS/TW/25/XXXX (SAMPLE)
> Policyholder N. Perera
> Vehicle three-wheeler NW QA-XXXX (SAMPLE)
> Period of insurance 21 Nov 2025 to 20 Nov 2026
> SAMPLE
> Page 1 of 2. SAMPLE document. Ceylon Shield Insurance is fictional.
> [Page 2]
> How to renew
> To renew, contact your agent with your policy number.
> Renew at least 7 days before the expiry date to avoid a gap in cover.
> Keep this schedule; you will need the policy number to renew.
> Renewal reminders are sent by SMS to the policyholder's registered mobile.
> SAMPLE
> Page 2 of 2. SAMPLE do

**Extract facts from a typed note** (0 redactions)

> Sunil drives airport runs every Thursday from 3.30 to 10 in the morning. The van driver Mr Silva collects the children at 6.45. His number is saved only on Nirmala's phone.

Facts extracted (first few): BUSY sunil = airport runs

**Listen to a 30-second voice note** (1 redactions)

> Hi, it's Nirmala. A few things for while I'm in Japan. Arti's clinic is every second Thursday at the district hospital and you have to leave by 7:00 in the morning to get a number. Her clinic book and the medicine list are in the top drawer of the steel cupboard. The gas shop's number is only on my phone, so I'll send it to Sunil before I go. Oh, and the pin for the bank app is [secret removed].

Facts extracted (first few): SCHEDULE r_clinic; ROUTE_WINDOW rt_clinic; STORED_ON gas_contact → nirmala_phone


## Router warnings

- model gemini-3.8-flash failed for reader: 
On how to mitigate this issue, please refer to:

https://google.github.io/adk-docs/agents/models/google-gemini/#error-code-429-resource_exhausted


429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more infor

This file is generated by `python -m evals.live_check`. It never contains the key.
