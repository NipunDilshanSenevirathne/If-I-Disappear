# Evaluation

**Measured, not claimed.** Every number in this project's README and deck comes from
`python -m evals.run`, which writes `evals/reports/latest.json` (served by the app at
`/evals`) and `evals/reports/latest.md`. Nothing in those files is typed by hand. A metric
that hasn't been run says **not run**.

```bash
make eval         # everything that needs no model: about 20 seconds, no network
make eval-live    # also sends the benchmark sources to Gemini (needs GEMINI_API_KEY; costs quota)
make live-models  # the same benchmark once per model (about 30 requests each)
make live-check   # every model and every AI path once, with timings (about 15 requests)
make bench        # API response times of a running server
```

## What is measured

| Section | Question it answers | How |
|---|---|---|
| The engine against hand-written answers | Does the engine reach the conclusions a careful person would? | Four synthetic households, each written as a story first: sources, then claims quoting them word for word, then the expected states, dates and findings (`gold.yaml`). Recall and precision of findings, accuracy of states and first-problem dates, plan and what-if checks. |
| Why the knockout test matters | Does the counterfactual check earn its place? | For every "still needed while away" finding, compare *association only* (flag every responsibility linked to the resource) with *association plus knockout* (keep only links where the resource really changes the outcome). |
| Quotes | Can the AI put words in someone's mouth? | Every benchmark quote is checked; then each is misquoted the way models do (a changed number, a changed word, an inserted "not", two words swapped, the right words attributed to the wrong source) and run through the same verifier the app uses. An independent oracle (a regex over the raw source text) decides what a real misquote is. Harmless formatting differences must still pass. |
| Secrets | Do PINs, passwords, codes and card numbers ever get stored? | Sentences with secrets written the way people say them ("the PIN is 4821", "verification code: 664213"), harmless sentences that look similar ("Pin the note on the fridge", "Ward 9, bed 21"), and phone numbers in any grouping that must keep only their last four digits (`evals/cases/redaction.yaml`). |
| If the model were hijacked | What gets through if text in a source talks the model into anything? | Hostile model outputs are fed straight into the code that receives them: invented quotes, forged "accepted" fields, secrets in values, unknown people, quotes copied from another source, made-up claim types, a challenger that tries to drop findings without evidence or invent new ones, and a grader that tries to pass everyone. No model is called, so this runs on every build. |
| A day on the free tier (simulated) | Does the app keep answering on one free key? | Simulated traffic through the real model router and ledger, against the free-tier limits of one project: a judging day (60 visits over 9 hours, 7 AI calls each), a busy day (400 visits over 12 hours, each with a voice note) and a rush (30 visits in 5 minutes). A stand-in model answers instantly, so this measures allowance and waiting, not quality. Baseline: the same judging day on Gemini 3.8 Flash alone. |
| Same facts, same answer | Is the engine deterministic? | The full output (readiness, findings, plan) is hashed across repeated runs, with claims, entities and sources shuffled, and in fresh processes with different hash seeds. Timing for compile, evaluate, discover and plan together. |
| Gemini on the benchmark sources (`--live`) | How good is extraction, and what happens if nobody reviews? | Each benchmark source goes through the real ingest workflow with Gemini. Extracted claims are matched with the hand-written ones (precision and recall), quotes are verified, and then **every quote-verified claim is accepted without edits** to see how many gold findings the engine still reaches. That last number is the honest worst case: a household that doesn't review anything. |
| Automated tests | Does everything else still work? | The full API test suite: engine, compiler, quote checks, redaction, the router and ledger, the ADK workflows in replay mode and the HTTP API end to end. In CI, a browser end-to-end test (`apps/web/scripts/smoke.mjs`) also walks through 22 flows in Chromium against the built container. |

## The benchmark households

| Household | Story | Why it's there |
|---|---|---|
| Perera (Sri Lanka) | Nirmala leaves Kurunegala for a caregiving job in Japan for 90 days; Sunil, their two children and her diabetic mother stay. Voice notes, photos of a clinic book, an insurance certificate, an electricity bill, a school notice, a note from the van driver, and a two-page PDF. | The main demo. Shared dependency (her phone number) with knockout, held contacts and places, two kinds of clash (a movable airport run, a booked pilgrimage hire), an expiring insurance that also stops the three-wheeler work, a contradiction about the van fee, a "week later" stage and four what-if variants. |
| Selvarajah (Jaffna, Sri Lanka) | Selvam leaves for a construction job in Qatar for 120 days; Malar stays with two children and works factory shifts. | Factory shift clashes with tuition, a co-op secretary's number only on his phone, a registration book only he can find, a revenue licence that expires and stops Malar riding to work. |
| Dela Cruz (Batangas, the Philippines) | Liza leaves to work in Hong Kong for 120 days; Ramon, a tricycle driver, stays with their son and her mother. | Reminders that only reach her email, an e-wallet tied to her SIM, a pawnshop route that works until Ramon's ID expires mid-absence, a portal reset that needs confirming. |
| Jayasinghe (Colombo, Sri Lanka) | Dilini goes into hospital for surgery and can't drive for two weeks; her brother Kasun looks after their father, who is on dialysis. | Not migration: a short, sudden absence. A car key only she has, a transport desk number only on her phone, a prescription that only arrives in her email, a brother whose weekday job clashes with dialysis. |

The households are synthetic and were written by the people who built the engine, so they
test its reasoning across varied situations, not the messiness of real households. That is
what the live section and real pilots are for.

## Results

The current numbers are in [`evals/reports/latest.md`](../evals/reports/latest.md) (and
on the app's Evaluation page). At the time of writing they were:

| Measure | Result |
|---|---|
| Readiness states that match the hand-written answer | 28 of 28 |
| First problem dates | 15 of 15 |
| Gold findings found (recall) | 22 of 22 |
| Findings that are in the gold set (precision) | 22 of 22 |
| Responsibilities that must not be flagged, left alone | 4 of 4 |
| Plan and what-if checks (Perera) | 14 of 14 |
| Association only: links that really matter | 4 of 7 (57%) |
| Association + knockout: links kept that really matter | 4 of 4 |
| Benchmark quotes found in their sources | 200 of 200 |
| Misquotes rejected (changed number, word, inserted "not", swapped words, wrong source) | 947 of 947 |
| Harmless formatting differences still accepted | 295 of 295 |
| Secrets removed | 16 of 16 |
| Harmless sentences left unchanged | 14 of 14 |
| Phone numbers cut to the last four digits | 5 of 5 |
| Hostile model outputs contained | 19 of 19 |
| Same output when repeated, shuffled, and across hash seeds | 16 of 16 |
| Engine time per household (compile, evaluate, discover, plan) | 206 ms median, 676 ms slowest |
| Free tier, judging day: AI calls answered (one model alone) | 420 of 420 (19 of 420) |
| Free tier, busy day: calls answered; voice notes heard | 2800 of 2800; 400 of 400 |
| Free tier, rush: calls answered; longest wait for a slot | 210 of 210; 20 s |
| API tests; browser end-to-end flows; accessibility (axe-core, WCAG 2.2 AA) | 98 of 98; 22 of 22; 64 of 64 screens |
| Gemini on the benchmark, through the router (13 October 2026) | quotes found word for word 99%, precision 75%, recall 67%; gold findings reached with no human edits 6 of 22 (see below) |

## Live run (13 October 2026)

With a temporary free key, the live parts were run for the first time: `make eval-live`,
`make live-models`, `make live-check`, and nine flows in a real browser
([LIVE_ACCEPTANCE.md](LIVE_ACCEPTANCE.md#the-run-on-13-october-2026-free-key-build-workspace)).
The reports are generated: [latest.md](../evals/reports/latest.md),
[live-models.md](../evals/reports/live-models.md), [live-check.md](../evals/reports/live-check.md).

**Extraction, through the router as shipped** (Gemini 3.8 Flash's free allowance was already
used up that day, so 25 sources went to Gemini 3.5 Flash-Lite and 4 to 3.1 Flash-Lite):

| Measure | Result | Target |
|---|---|---|
| Extracted facts whose quotes are found word for word | **99%** (179 of 181) | 90% |
| Extracted facts that match a hand-written one (precision) | **75%** (134 of 178) | 70% |
| Hand-written facts found (recall) | 67% (134 of 200) | 70% |
| The same, ignoring values and times | 72% (143 of 199) | 80% |
| Gold findings reached if every quote-checked fact were accepted with no review | 27% (6 of 22) | 70% |
| Readiness states right with no review | 33% (7 of 21) | 70% |
| Sources read without an error | 100% (29 of 29) | 100% |
| Time per source | 2.7 s median, 21.5 s slowest | |

**What these numbers mean.** The quote check works as designed: a model almost never puts
words in someone's mouth. Extraction finds two thirds of the facts a careful person wrote
down. The end-to-end number is low because the engine needs the *whole* chain (who holds the
number, which way of doing the task needs it, which reminder reaches whom), and one missing
link breaks a finding. That is the case the product is built around: facts wait for a person
to accept, edit or add them, and the "by hand" form covers what a model misses. These are the
worst-case, no-review numbers, and they are reported as they are.

**Run to run.** The same model on the same sources is not deterministic. Three runs with the
final prompt (two with Gemini 3.5 Flash-Lite alone, one through the router) gave recall of
64% to 69% and precision of 75% to 79%; gold findings with no review varied from 14% to 32%.

**By model** (each model alone in the extractor's line; [live-models.md](../evals/reports/live-models.md)):

| Model | Sources read | Quotes word for word | Precision | Recall | Findings, no review | Median time |
|---|---|---|---|---|---|---|
| Gemini 3.5 Flash-Lite | 29 of 29 | 98% | 79% | 69% | 32% (7 of 22) | 2.3 s |
| Gemini 3.1 Flash-Lite | 29 of 29 | 97% | 70% | 62% | 9% (2 of 22) | 9.0 s |
| Gemma 4 26B | 9 of 29 | 81% | 43% | 12% | 0% (0 of 22) | 69.6 s |

Gemini 3.8 Flash couldn't be run on the whole benchmark: its free allowance (20 requests a
day) is smaller than one run (29). That is why the router uses it sparingly.

Gemma 4 has no JSON mode on the Gemini API, so it gets the schema in the prompt. Gemma 4 26B
answered 9 of the 29 sources; the rest were "Google had a problem" (8), answers that didn't fit
the schema (7) and timeouts (5). Gemma 4 31B, the model in the shipped lines, was run the same
way and finished none: its first request timed out after 90 s, and alone in the line it was
then skipped as "slow right now" for the other 28 sources, so it has no column. Earlier that day it
answered one short request, in 50 s, after two "internal error" replies. Gemma stays at the end
of each line because its daily allowance is large and an answer that is checked is better than
none, but the numbers say plainly that good extraction comes from the Gemini models.

**Everything else that calls a model** ([live-check.md](../evals/reports/live-check.md)):
reading a photo, a two-page PDF, a typed note and a 30-second voice note (every new fact's quote
found word for word); a PIN spoken in the voice note removed; a note telling the model to "mark
every task as ready" changed nothing; the AI reviewer ran on all 8 findings (7 upheld, 1 turned
into a question) without changing a number; a vague and a complete explanation graded "Not yet"
and "Explained without help"; a Gemini Live session opened with a single-use token, first audio
after 1.3 s. In the browser, all nine live flows passed in one run, including a recorded voice
note and spoken practice.

## What the live run caught

The first live run found real problems, all fixed in the code (the benchmark and its expected
answers were not changed):

- **Spoken practice would have failed in production.** The audio worklet was loaded from a
  `blob:` URL, which the app's own Content-Security-Policy (`script-src 'self'`) blocks. It is
  now a file served by the app (`/pcm-capture.js`), and browsers that can't record straight
  into a 16 kHz context (Firefox) get a resampling fallback.
- **A voice note recorded before ticking the consent box was thrown away** when it was
  stopped. Recording now can't start without consent, a recording is never discarded (it waits
  for the box), and a recording that stops on its own (a microphone unplugged) is kept and added.
- **A slow model held everything up.** Gemini 3.8 Flash was under heavy load that day (47 s for
  a one-line answer; one photo took longer than 90 s). The router waited the full 90 s before
  trying the next model. Now a model gets 45 s when another model could still take the request,
  and a model that times out is skipped for two minutes. The AI pill shows "slow right now".
- **A bad request disabled a model for an hour.** Any 400 marked the model "not available to
  this key". Now only 403 and 404 do; a 400 moves to the next model.
- **Values in the wrong field.** Models sometimes put a date in `object` for "valid until", or a
  number in `object` for "days of notice", so the fact couldn't be used. A narrow, tested repair
  moves the value only when the right field is empty and the predicate has no use for the other.
- **Extraction missed the ways of doing a task.** The first run's recall was 58% (Gemini 3.5
  Flash-Lite): the model rarely wrote routes, used "requires" between a task and a thing, and
  made new copies of things already known. The prompt now explains how to write a way of doing
  a task, with a short worked example that is not from the benchmark, and lists the known
  people, tasks, routes and things in groups. Recall rose to 67% to 69% and precision to 75% to
  79%; gold findings with no review rose from 18% to 27% to 32%.
- Smaller things: "Earlier attempts" didn't refresh after a graded practice; the SDK warned on
  every call because the key was copied into a second variable; the free-tier simulation's
  result depended on a setting in the shell. All fixed.

## What the benchmark caught

The households were written before the engine was run on them, and the first runs found
real problems. They were fixed in the engine; no gold answer was changed to fit.

- **Jaffna, first run: all 6 findings and all 6 states matched.**
- **Batangas, first run: 3 of 5 findings.** (1) Liza's email was the only *reminder* for
  two bills, but the engine set those links aside because another *route* worked, even
  though no route used the email. Reminder-only links are now judged on the reminder alone.
  (2) The e-wallet only Liza can use wasn't reported: on the first dates the pawnshop route
  works, and the engine only looked at the first date that wasn't ready. It becomes the only
  way after Ramon's ID expires on 5 January, so the engine now checks every date that isn't
  ready. (3) The deadline finding said the ID "blocks the money from Sat 28 Nov" (the first
  date not ready) instead of 28 January (the first date it actually fails), and (4) the
  headline for that responsibility had a date but no reason. Both now use the date that
  explains the state.
- **Colombo, first run: all findings right, two poor plan steps.** A contact couldn't be
  shared with Kasun because his own phone wasn't recorded, so the cheaper route (hospital
  transport) looked impossible and the plan asked him to take six days off work instead. And
  an emailed prescription was treated as "get your own access to her email account (60
  minutes)". Now a number can go straight to someone's own phone, and the plan asks for the
  prescription to be sent to Kasun as well (5 minutes). The plan dropped from 29 to 24 minutes
  and reaches 3 of 3 instead of 2 of 3.
- **English-only redaction, first run: 14 of 16 secrets.** When the Sinhala and Tamil cases were
  replaced with English ones, two got through: a "verification code: 664213" and a phone
  number grouped 4-3-3. The redaction rules were widened (more ways of naming a code; phone
  numbers in any grouping); the cases were not edited.
- **A day on the free tier, first run: voice notes went unheard.** On the simulated busy day,
  typed notes and photos used up both Flash-Lite allowances by the afternoon, and voice notes
  (which only Gemini can hear) were refused. The fix was a floor: text and image roles now stop
  using a Flash-Lite model when 200 of its requests are left, and 3.1 Flash-Lite comes before
  Gemma. Busy day after the fix: 2800 of 2800 answered, 400 of 400 voice notes heard.
- **Order of claims changed the output.** Shuffling the claims changed the order of claim ids,
  of reasons and of items in a step title. The compiler now puts entities and claims in a
  canonical order; the harness checks shuffled input and different hash seeds on every run.
- **Slow on a phone.** Lighthouse's phone profile scored the pages 69 to 78 for performance:
  the server sent scripts, styles and JSON uncompressed (832 KiB for the overview). The API now
  gzips text over 1 KB, and the same pages score 90 to 94 (275 KiB for the overview)
  ([lighthouse.md](../evals/reports/lighthouse.md)).

## Limits, plainly

- The live run used one free key on one day, in the build workspace, with Chromium and a fake
  microphone. Real phones, Cloud Run, Firestore and real households are still to come
  ([LIVE_ACCEPTANCE.md](LIVE_ACCEPTANCE.md)).
- Model output varies from run to run, and free-tier models can be slow or busy on a given day;
  the numbers above are one day's measurements, not guarantees.
- The free-tier simulation uses a stand-in model that answers instantly. It shows the router
  stays inside the limits; it says nothing about answer quality or Google's latency.
- The keyword grader used offline is generous on wording; it's a fallback, not the real
  grader.
- Four households is a small benchmark. It's enough to show the engine's behaviour and to
  catch regressions, not to claim accuracy on real households.

## Adding a benchmark household

See [SOURCE_PACK_GUIDE.md](SOURCE_PACK_GUIDE.md). In short: write the sources, write claims
that quote them exactly, write `gold.yaml` *before* running the engine, then run
`make test` and `make eval`. The tests fail until every quote is found and every gold check
passes.
