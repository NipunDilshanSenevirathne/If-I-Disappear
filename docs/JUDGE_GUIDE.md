# A five-minute tour for judges

Open the deployed link and press ** See a family's plan**. You get your own private copy of the
Perera household; nothing you do affects anyone else, and **Reset** in the sample bar puts it
back. Everything in it is made up. A 12-step quick tour starts by itself; you can skip it and
take it again from the top bar.

> The pill at the top right says **Offline demo** when the deployment has no Gemini key: AI
> steps replay reviewed sample answers and say so. With a key it says **Free AI · N left today**
> and opens to show each model's allowance, live. The engine, findings and plan are the same
> code either way. Everything that calls a model was tested live with a free key on 13 October
> 2026: 13 of 13 AI paths and 9 of 9 browser flows passed ([LIVE_ACCEPTANCE.md](LIVE_ACCEPTANCE.md)).

## 1. The question (30 seconds)

**Overview.** Nirmala leaves for a caregiving job in Japan on 1 November for 90 days. Her
husband Sunil, their two children and her diabetic mother stay. The headline answers the
question the app is named after: **1 of 7 things are ready**. The week chart shows where the
absence breaks (hover or use the arrow keys); the donut, the trend and the calendar all update
by themselves when anything changes. Open a responsibility for every date and the reason:
*"Blocked on Thu 5 Nov. Sunil is busy on Thu 5 Nov (airport runs, 03:30–10:00), and this needs
06:30–07:00."*

## 2. What nobody said (1 minute)

**What we found.** Open *Nirmala's phone number is still needed for 2 things*. The number
appears in six sources next to four responsibilities. An association-only tool would flag all
four. The engine re-ran the absence as if the number stayed available and kept only two: the
school messages (nothing else works) and the insurance renewal (its only reminder). It shows the
two it **set aside**, and why: the clinic dates are also in the clinic book; the electricity
bill can be paid in cash at the post office.

Look at the reeded glass on *Some contacts are only on Nirmala's phone*: what only she holds is
blurred until it's handed over. Answer *"Ask Sunil: can you pay the electricity bill?"* right on
the card and watch the numbers move.

## 3. What if…? (30 seconds)

**Explore.** Switch on *Sunil* under "Who else is away?": ready drops from 1 to 0 instantly, and
the list says why ("Only Nirmala has the Lanka Savings app, and Nirmala is away"). Try a missing
phone or a longer absence. It's the same engine on a copy; nothing is saved and no AI is used.

## 4. The smallest plan, and proof (1 minute)

**Plan.** Choose 30 minutes, 1 hour, 1 h 30 or 2 hours. The optimiser searches every combination
of fixes and picks the one that gets the most done in the time you have: **67 minutes gets 6 of
7 ready**, 41 for Nirmala and 26 for Sunil. One date stays open on purpose (Sunil's booked
pilgrimage hire on 24 December), and the plan says so. Press **Mark done** on a step: it asks
how you know (an agreement, a photo…), then the numbers move.

In the sample bar, **Jump a week ahead**: the family recorded agreements, photos and practice,
and the same engine now says **6 of 7 ready**, matching the plan's prediction because both use
the same typed effects.

## 5. Practise and hand over (1 minute)

**Practise.** Sunil explains *Pay the electricity bill* in his own words. With a key, press the
microphone: a Gemini Live partner sets the scene, listens and grades the transcript against
the approved steps. Without a key, type it. Try a vague answer, then a complete one: every key
step must be covered, and a hint means "practised with help".

**Card**: one printable page for the fridge, no passwords, PINs or account numbers. **Share**:
make a private link for Sunil and open it (QR code or "See what they'll see"): only his part of
the card, with practice, on his own phone. Switch it off again.

## 6. Under the hood (2 minute)

- **Capture** → **Photo or PDF** → pick a sample document (an electricity bill photo). Watch
  each workflow step and the model that answered it; then **Review facts** shows every fact with
  the exact words it came from.
- **How it was worked out**: the full check as a flow ("AI reads" vs "code decides"); press
  **Check again with AI** to run it and see each step's model and timing.
- The **AI pill**: today's allowance for Gemini 3.8 Flash, 3.5 and 3.1 Flash-Lite and Gemma 4,
  and which model does what. This is how it runs on the free tier.
- **Evaluation** (left menu or landing page): the generated report, from the live run with a
  free key on 13 October 2026. 38 checks pass and 4 fail; the 4 measure Gemini's extraction with
  nobody reviewing the facts (the worst case), and the page says what that means. Run
  `make eval` locally and the same report is rebuilt without a key (the live checks then say
  **not run**).

Other sample families are in the sample bar's menu: **Selvarajah** (Jaffna, Qatar), **Dela Cruz**
(Batangas, Hong Kong) and **Jayasinghe** (Colombo, a two-week hospital stay).


The project's original build specification set 17 steps that had to work end
to end. All of them do:

| # | Must work | Where |
|---|---|---|
| 1 | Create a household | **Start your own household**, or open a sample one |
| 2 | Upload documents | Capture: photos, PDFs, or a sample document |
| 3 | Voice or text statement | Capture: talk, type, or a short form |
| 4 | Gemini extracts claims | Ingest workflow (extractor agent), with verbatim quotes |
| 5 | Evidence graph updates | Review facts: each tied to the exact words it came from |
| 6 | Discovery finds a hidden relationship | What we found |
| 7 | Peer review checks it | Quote verifier and the AI challenger |
| 8 | Red team challenges it | Challenger: uphold, narrow (with cited facts) or ask |
| 9 | Verifier commits it | Code checks citations; people accept facts |
| 10 | Remove a person in simulation | The absence itself; Explore; what-if variants |
| 11 | Deterministic cascade | The engine: dates, states, reasons |
| 12 | Repair planner proposes fixes | Plan, within a time budget |
| 13 | Assign a backup | Plan bundles name who takes it over; record agreement |
| 14 | Handover coach teaches | Gemini Live practice partner; the person staying's own link |
| 15 | Handover exam tests | Teach-back graded against approved steps |
| 16 | Simulation reruns | After every recorded step, automatically |
| 17 | Resilience metrics change | 1 of 7 ready before, 6 of 7 after; the trend chart shows it |
