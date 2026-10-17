# Roadmap

The prototype is the first slice of a bigger idea in the project's master specification
(*Continuum*): a resilience engine for any system that quietly depends on one person.
We built the slice that has to work end to end first, and kept the rest out until the core
was solid.

## Built now

| Area | What works |
|---|---|
| Capture | Voice notes (converted to 16 kHz WAV in the browser), photos, PDFs, typed notes and a short form with no AI; eight sample documents; consent before sending; redaction before anything is stored |
| Understand | Gemini extraction into small facts with exact quotes; quote verification; entity resolution; household review with edit, dispute and undo |
| Free tier | A model router over Gemini 3.8 Flash, 3.5 and 3.1 Flash-Lite and Gemma 4: per-model ledger, floors per role, capability matching, fallback, schema validation, a response cache, a fair share per visitor, a live allowance meter |
| Model | Responsibilities, routes, resources, containers, permits and renewals, people's commitments, facts, handover evidence |
| Simulate | Day-by-day evaluation of the absence in three-valued logic; five readiness states with a reason and a date |
| Discover | Still needed while away (with counterfactual knockout), held by the person leaving, clashes, deadlines, not asked, contradictions |
| Challenge | An AI reviewer that can uphold, narrow (with cited claims) or question each finding, checked by code |
| Repair | Typed plan steps with effects; exhaustive search within a time budget; honest about what stays open |
| Prove | Recorded evidence applies the same effects; "a week later" stage; what-if variants |
| Explore | Instant what-ifs on a copy: someone else away, a thing missing, an assumption undone, a different length |
| Handover | Approved steps (drafted from the household's own claims); teach-back by voice (Gemini Live) or text; graded by code |
| Share | A printable Continuity Card with no secrets; a private, revocable link per person staying, with practice on their own phone |
| Interface | Live dashboard (week bars, donut, trend with the plan's projection, calendar), a 12-step quick tour, light and dark themes, phone layout, keyboard and reduced-motion support |
| Measure | A generated evaluation report: gold households, ablation, misquotes, secrets, hijacked-model containment, determinism, live extraction; live checks of every model and AI path, nine live browser flows, API timings, Lighthouse and accessibility |

## Next (the three months after the Cup)

1. **A small pilot with real families**, through organisations that already support migrant
   workers' families, with informed consent and a clear way to delete everything. Measure
   what we can't measure on synthetic data: how many findings families say they would have
   missed, how long the plan really takes, what still went wrong in the first month.
2. **A live acceptance run on real phones and on the deployed service** with Firestore
   ([LIVE_ACCEPTANCE.md](LIVE_ACCEPTANCE.md)). Every AI path already passed with a free key in
   the build workspace on 13 October 2026, and the live numbers are in the report.
3. **Reminders that reach the person staying**: the Continuity Card's dates as SMS or
   messaging reminders on their own phone, so nothing depends on the leaver's number.
4. **Works on a weak connection**: an installable web app that keeps the card, the plan and
   practice available offline and syncs when it can.
5. **Ask**: questions in plain language ("What do I need for the clinic on Thursday?")
   answered only from accepted claims, with the quotes.
6. **Keep it fresh during the absence**: re-check dates monthly, prompt a short practice
   before a rare task comes due, and notice when a fact goes stale (a new phone number, a
   moved appointment).
7. **More than one absence at a time**: both parents away, or the backup falling ill.

## Later

- **Capability substitution**: "nobody at home can drive" → find a neighbour, a service or a
  different route, with the cost of each.
- **Community and helper mode**: a trusted helper outside the house (a cousin, a neighbour)
  with access limited to the tasks they agreed to.
- **On-device extraction with Gemma** for households that don't want their voice notes to
  leave the phone.
- **Small organisations**: the same engine for a shop when the owner travels, a family
  business, a care team or a school office ("what breaks if the only person who knows payroll
  is away?").
- **Agent-to-agent and MCP integrations**: let a bank, a school or a clinic confirm a fact
  ("Sunil's number is now registered") directly, instead of a person typing it in.

## What we will not build

- A password vault, or anything that stores secrets.
- Location tracking or reading people's phones. The app works *with* a family, not on them.
- Automatic decisions about people. The app asks; people decide.
