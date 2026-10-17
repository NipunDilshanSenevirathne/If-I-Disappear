# Running on the free Gemini tier

The competition asks for an app people can open and use. A free Gemini API key from Google AI
Studio is enough to run this one all day, because the AI work is spread over several Google
models, each kept within its own free limits. This page explains how, what was measured, and
what to change for a paid key.

## The limits we design for

Google's free tier limits each model **per project**, in three ways: requests per minute (RPM),
input tokens per minute (TPM) and requests per day (RPD, reset at midnight Pacific time). The
numbers below are the ones Google AI Studio showed for a free project in October 2026. They
are settings, not code: override any of them with `QUOTA_LIMITS`.

| Model | RPM | TPM | RPD | Reads | Used for |
|---|---:|---:|---:|---|---|
| Gemini 3.8 Flash | 5 | 250,000 | **20** | text, images, audio, PDF | first choice for the hardest steps, used sparingly |
| Gemini 3.5 Flash-Lite | 15 | 250,000 | 500 | text, images, audio, PDF | the everyday workhorse |
| Gemini 3.1 Flash-Lite | 15 | 250,000 | 500 | text, images, audio, PDF | a second workhorse with its own allowance |
| Gemma 4 31B | 30 | 16,000 | 14,400 | text, images | text and image fallback with a large daily allowance |
| Gemma 4 26B | 30 | 16,000 | 14,400 | text, images | available as an alternative (not in the default lines) |
| Gemini 3.8 Live | — | 65,000 | — | voice, live | spoken practice |

With one model alone (Gemini 3.8 Flash) a free key answers about 20 AI requests a day: one
family reading a few notes would use it up before lunch. Together the models allow well over
a thousand requests a day.

## How the router works

Every AI step in the app has a **role**, and each role has a **line of models**, best first:

| Role | What it does | Line of models (default) |
|---|---|---|
| Listener | writes down a voice note | 3.8 Flash (keeps 8) → 3.5 Flash-Lite → 3.1 Flash-Lite |
| Reader | reads a photo or a PDF | 3.8 Flash (keeps 8) → 3.5 Flash-Lite (keeps 200) → 3.1 Flash-Lite (keeps 200) → Gemma 4 31B |
| Extractor | turns text into facts with quotes | same as the reader |
| Challenger | the second reader of each finding | 3.8 Flash → 3.5 Flash-Lite (keeps 200) → 3.1 Flash-Lite (keeps 200) → Gemma 4 31B |
| Grader | checks a typed or spoken explanation | 3.5 Flash-Lite (keeps 200) → 3.1 Flash-Lite (keeps 200) → Gemma 4 31B → 3.8 Flash (keeps 8) |

For each call the router walks down the line and uses the first model that:

1. **can read the input.** Audio and PDFs only go to Gemini models; Gemma is skipped for them,
   and the step says so ("skipped: Gemma 4 31B, can't read this kind of file").
2. **has allowance left above its floor.** "Keeps 200" means a role stops using that model when
   only 200 of its daily requests are left, leaving them for roles that have no other choice.
   Voice notes can only use Gemini, so text and photo steps leave the last Flash-Lite requests
   to them. That is how a busy day of typed notes never leaves a voice note unheard.
3. **has a free slot this minute.** If the per-minute limit is reached, the router waits for
   the next slot (up to `AI_MAX_WAIT`, 20 s by default) before trying the next model.
4. **answers properly, in time.** A 429 ("slow down") marks the model as cooling down and moves
   on; a 5xx cools it down for 20 seconds; a model that takes longer than 45 s (when another
   model could still take the request) is skipped for two minutes; a 400 or an answer that
   doesn't fit the schema moves on to the next model; only a 403 or 404 marks a model as not
   available to this key.

Gemini models answer in native JSON mode with the schema attached. Gemma models get the same
schema written into the prompt; their answer is parsed and validated exactly the same way. If
every model in a line is busy or used up, the step fails with a plain message ("No AI model
could take this right now (…the reason for each model…). The rest of the app keeps working."),
and nothing else in the app is affected: the engine, the plan, the card, Explore and adding
facts by hand need no AI at all.

Three more things keep the allowance for real work:

- **No asking twice.** Identical requests (same prompt, same file) reuse the first answer for
  up to three days. Reading the same sample document again costs nothing.
- **A fair share per visitor.** `AI_CALLS_PER_VISITOR` (40 on the deployed app) stops one
  visitor using the whole day's allowance. When it's reached, the visitor is told so, and that
  everything else still works and facts can be typed in by hand.
- **Engine refreshes are free.** After every change (accepting a fact, answering a question,
  recording a step) the deterministic engine recomputes everything without a model. Only
  "Check again with AI" runs the reviewer.

## What a real day looked like (13 October 2026)

The router was run live for one day on a free key ([LIVE_ACCEPTANCE.md](LIVE_ACCEPTANCE.md)):

- **Gemini 3.8 Flash was the busy one.** Google answered "high demand" (503) several times and
  one short request took 47 s. After its first timeout the router skipped it for two minutes
  ("slow right now" in the AI pill); by midday its 20 free requests were used up and every later
  step went to Gemini 3.5 Flash-Lite without anything failing.
- **Gemini 3.5 Flash-Lite carried the day**: typically 1 to 3 s per step (reading a photo,
  extracting facts, reviewing findings, grading), and the best extraction quality of the free
  workhorses ([EVALUATION.md](EVALUATION.md#live-run-13-october-2026)).
- **Gemini 3.1 Flash-Lite** answered every request but was slower that day (9 s median per
  extraction, one at 212 s), which is why it comes second in each line.
- **Gemma 4 is a last resort, not a peer.** With the schema written into the prompt, Gemma 4
  26B finished only 9 of 29 benchmark extractions (the rest: answers that didn't fit the schema,
  internal errors, timeouts), and Gemma 4 31B mostly answered "internal error" to the first
  request. The router keeps Gemma at the end of each line for availability, the quote check
  rejects anything it can't prove, and people review every fact; for real use, plan on the
  Gemini models' allowance.
- **The cache earned its place**: re-reading the same sample photo reused the first answer
  ("7 answers reused for identical requests"), at no allowance.

## What you can see

- The **AI pill** in the top bar shows how many requests are left today across the models.
  Open it for each model's use today and this minute, cooling-down timers, and which model
  does what. It updates every ten seconds.
- Every workflow step in **Capture**, **How it was worked out** and the check dialog shows the
  model that answered it, and any model it skipped and why.
- `GET /api/ai/usage` returns the same numbers as JSON.

The ledger is saved once a minute (to Firestore when deployed), so a restart doesn't forget
today's counts. Deploy with `MAX_INSTANCES=1` on the free tier so one instance keeps one
accurate count; one instance serves many visitors at once.

## Measured

`make eval` simulates whole days of traffic through the real router and ledger (with a stand-in
model that answers instantly), against the limits above:

| Scenario | Calls answered | By model |
|---|---|---|
| Judging day: 60 visits over 9 hours, 7 AI calls each | **420 of 420** | 3.5 Flash-Lite 292, 3.1 Flash-Lite 109, 3.8 Flash 19 |
| Busy day: 400 visits over 12 hours | **2800 of 2800**; voice notes heard 400 of 400 | Gemma 4 31B 1876, 3.5 Flash-Lite 475, 3.1 Flash-Lite 430, 3.8 Flash 19 |
| Rush: 30 visits in 5 minutes | **210 of 210**, longest wait 20 s | 3.5 Flash-Lite 134, 3.1 Flash-Lite 52, 3.8 Flash 19, Gemma 4 31B 5 |
| Baseline: Gemini 3.8 Flash only, judging day | 19 of 420 | — |

This measures allowance and waiting, not answer quality or Google's speed. Quality with a real
key is measured by `make eval-live` ([LIVE_ACCEPTANCE.md](LIVE_ACCEPTANCE.md)).

On the busy day, two thirds of the answers come from Gemma 4 31B, and the live run showed Gemma
is much slower and weaker than the Gemini models at this task. So the busy day shows the app
stays up and every voice note is still heard; it doesn't show the answers stay as good. A real
service at that volume should use a paid key (`QUOTA_TIER=paid`): see the cost section of
[SUBMISSION_ANSWERS.md](../SUBMISSION_ANSWERS.md#6-estimated-implementation-cost).

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `QUOTA_TIER` | `free` | `paid` keeps counting (for the meter) but never refuses on the free limits |
| `QUOTA_LIMITS` | — | JSON overrides per model, e.g. `{"gemini-3.8-flash": {"rpm": 10, "rpd": 250}}` |
| `QUOTA_RESERVE` | `0.05` | the share of each daily allowance never used (a safety margin for retries) |
| `AI_CHAIN_LISTENER`, `_READER`, `_EXTRACTOR`, `_CHALLENGER`, `_GRADER` | see above | your own line of models: `gemini-3.5-flash-lite:keep=100, gemma-4-31b-it` |
| `AI_CALLS_PER_VISITOR` | `0` locally, `40` deployed | AI calls per visitor per day (0 = no limit) |
| `AI_MAX_WAIT` | `20` | seconds to wait for a per-minute slot before trying the next model |
| `AI_TIMEOUT` | `90` | seconds before a model call is given up |
| `AI_TRY_TIMEOUT` | `45` | a shorter limit when another model in the line could still take the request; a model that times out is skipped for two minutes |
| `MODEL_LIVE` | `gemini-3.8-live` | the spoken practice model |

## What we don't do

- **We don't rotate keys or accounts** to get more allowance. Google's API terms forbid getting
  around usage limits; the router stays inside one project's published limits.
- **We don't send secrets.** Typed text is redacted before any model sees it.
- **We don't hide the free tier's data terms.** On unpaid services Google may use what it is
  sent to improve its products, and people may review it. The app asks before sending anything,
  and every sample is made up. For a real household, use a paid key or Vertex AI and set
  `QUOTA_TIER=paid`.
