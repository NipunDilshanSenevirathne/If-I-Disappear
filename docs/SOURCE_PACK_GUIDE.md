# Writing a sample household (a "source pack")

The sample households in `services/api/fixtures/households/` are the demo data and the
benchmark. Each one is a folder:

```text
household.yaml   settings, people, tasks, routes, things, facts, and (optionally) approved steps
sources.yaml     what the family "recorded": voice notes, photos, PDFs, typed notes (as text)
claims.yaml      the reviewed claims, each quoting a source word for word
gold.yaml        what the engine should conclude, written BEFORE running it
evidence.yaml    optional: a "week later" stage (agreements, photos, practice)
variants.yaml    optional: what-if variants
files/           optional: rendered sample images and PDFs (marked SAMPLE)
```

Add the household to `fixtures/households/demos.yaml` to make it openable from the app.

## Rules that keep it honest

1. **Story first.** Write who leaves, where to, for how long, who stays, and what goes wrong.
   Every name, number, provider and document must be fictional; mark documents `SAMPLE`
   and mask phone numbers (`077-XXX-4567`).
2. **Sources sound like people.** Short voice notes in the speaker's words (in English), photos
   of documents as their visible text. To render a source as a sample image or PDF, use
   `apps/web/scripts/render-samples.mjs`; every rendered file says SAMPLE.
3. **Every claim quotes its source exactly.** Use the shortest quote that proves it.
   `derivation: model_inference` (with a `note`) when part of it is inferred, for example
   reading "every morning" as a window.
4. **Write `gold.yaml` before you run the engine.** States, first-problem dates, the findings
   you expect (id, kind, responsibilities; for shared dependencies, which links are retained
   and which are set aside, with the code), and responsibilities that must *not* be flagged.
5. **Don't edit gold to make a test pass.** If the engine disagrees, decide who is right. If
   the engine is wrong, fix the engine and say so in [EVALUATION.md](EVALUATION.md).

## Checking it

```bash
make test   # every quote must be found; the household must compile cleanly; gold must match
make eval   # the report counts the new household in every section
```

To see what the engine thinks while you write:

```bash
cd services/api
../../.venv/bin/python - <<'EOF'
from app.verify.gold import check_household, run
r = run("your_household", budget=60)
for rid, x in r.result.results.items():
    print(rid, x.state.value, x.first_problem)
for f in r.findings:
    print(f.id, f.kind, f.responsibilities, "|", f.summary)
print([c.describe() for c in check_household("your_household").checks if not c.ok])
EOF
```

## Predicates you'll use most

| Predicate | Example |
|---|---|
| `DOES person -> responsibility` | Nirmala pays the electricity bill |
| `CAN_DO person -> responsibility` (`yes`, `no`, `unsure`) | Sunil can pay the van fee if the money is left ready |
| `SCHEDULE responsibility` | monthly on the 10th; every second Thursday from 12 Nov |
| `ROUTE responsibility -> route` | pay on the bank app; pay cash at the post office |
| `ROUTE_NEEDS route -> resource` | the post office route needs the paper bill |
| `ROUTE_WINDOW route` | 07:00–11:30 |
| `HOLDS person -> resource` | only Nirmala knows where the clinic book is |
| `STORED_ON resource -> container` | Mr Silva's number is saved on Nirmala's phone |
| `NOTIFIES resource -> responsibility` | the clinic book has the next date |
| `VALID_UNTIL permit` and `RENEWS responsibility -> permit` | the insurance ends on 20 Nov 2026 |
| `BUSY person` (with `fixed: true` if it can't be moved) | airport runs on Thursdays 03:30–10:00 |
| `FACT fact` (`yes`, `no`, `unsure`) | the school resets portal passwords on request: unsure |
| `IMPORTANCE responsibility` (1–3) | 3 for health, income or legal |

The full list, with meanings, is in `services/api/app/domain/claims.py` and in the
extractor's prompt (`services/api/app/ai/prompts/extractor.md`).
