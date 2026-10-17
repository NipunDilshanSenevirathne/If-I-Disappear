## What changes

<!-- One or two sentences, in plain words. -->

## How it was checked

- [ ] `make test` (API tests, no network)
- [ ] `make lint` (ruff and TypeScript)
- [ ] `make eval` is still at 0 failed (attach `evals/reports/latest.md` if numbers moved)
- [ ] `make serve` + `make smoke` (browser end-to-end), if the web app changed
- [ ] Screenshots in light and dark, desktop and phone, if a screen changed

## The rules (see AGENTS.md)

- [ ] The AI reads; code decides. No model output can change a state, date, count, plan or grade without deterministic code in between.
- [ ] No secrets stored or shown; new free-text inputs go through `ai/redact.py`.
- [ ] Evaluation numbers come from the harness, never typed by hand.
