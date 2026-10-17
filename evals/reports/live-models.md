# Extraction quality by model

Generated 2026-10-13T08:50:49+00:00 by `python -m evals.live_models`, on the four benchmark households (29 sources), through the app's real ingest workflow: the model extracts claims with quotes, code checks every quote. Each column is one model alone in the extractor's line (free tier). The hand-written claims and expected findings are the same ones the offline report uses.

| Metric | Target | Gemini 3.5 Flash-Lite | Gemini 3.1 Flash-Lite | Gemma 4 26B |
|---|---|---|---|---|
| Claims Gemini extracted that match a hand-written claim (precision) | ≥ 70% | 79% (138/174) ✓ | 70% (124/178) ✗ | 43% (23/54) ✗ |
| Hand-written claims Gemini found (recall) | ≥ 70% | 69% (138/200) ✗ | 62% (124/200) ✗ | 12% (23/200) ✗ |
| Same, ignoring values and times (recall) | ≥ 80% | 74% (147/199) ✗ | 65% (130/199) ✗ | 15% (30/199) ✗ |
| Extracted claims whose quotes are found word for word | ≥ 90% | 98% (173/176) ✓ | 97% (176/181) ✓ | 81% (44/54) ✗ |
| Gold findings reached with no human edits | ≥ 70% | 32% (7/22) ✗ | 9% (2/22) ✗ | 0% (0/22) ✗ |
| Readiness states right with no human edits | ≥ 70% | 38% (8/21) ✗ | 33% (7/21) ✗ | 10% (2/21) ✗ |
| Sources processed without an error | 100% | 100% (29/29) ✓ | 100% (29/29) ✓ | 31% (9/29) ✗ |
| Time per source, median |  | 2.3 s | 9.0 s | 69.6 s |
| Time per source, slowest |  | 63.9 s | 212.1 s | 124.6 s |

| Model | Minutes for the run |
|---|---:|
| Gemini 3.5 Flash-Lite | 2.3 |
| Gemini 3.1 Flash-Lite | 7.4 |
| Gemma 4 26B | 28.7 |

**Gemini 3.5 Flash-Lite**

- batangas: 33/48 claims matched, 41 distinct extracted, gold findings reached 2/5, states 1/5
- colombo_care: 22/28 claims matched, 27 distinct extracted, gold findings reached 1/3, states 2/3
- jaffna: 33/45 claims matched, 39 distinct extracted, gold findings reached 1/6, states 2/6
- perera: 50/79 claims matched, 67 distinct extracted, gold findings reached 3/8, states 3/7
- Extractions answered by: Gemini 3.5 Flash-Lite 29

**Gemini 3.1 Flash-Lite**

- batangas: 27/48 claims matched, 40 distinct extracted, gold findings reached 0/5, states 1/5
- colombo_care: 19/28 claims matched, 29 distinct extracted, gold findings reached 0/3, states 1/3
- jaffna: 29/45 claims matched, 39 distinct extracted, gold findings reached 0/6, states 3/6
- perera: 49/79 claims matched, 70 distinct extracted, gold findings reached 2/8, states 2/7
- Extractions answered by: Gemini 3.1 Flash-Lite 29

**Gemma 4 26B**

- batangas: 13/48 claims matched, 25 distinct extracted, gold findings reached 0/5, states 1/5
- colombo_care: 2/28 claims matched, 3 distinct extracted, gold findings reached 0/3, states 0/3
- jaffna: 5/45 claims matched, 13 distinct extracted, gold findings reached 0/6, states 0/6
- perera: 3/79 claims matched, 13 distinct extracted, gold findings reached 0/8, states 1/7
- Extractions answered by: Gemma 4 26B 9
- error in batangas/B02: AIUnavailable: No AI model could take this right now (Gemma 4 26B: Google had a problem). The rest of the app keeps working.
- error in batangas/B04: AIUnavailable: No AI model could take this right now (Gemma 4 26B: answer didn't fit the expected form). The rest of the app keeps working.
- error in colombo_care/K01: AIUnavailable: No AI model could take this right now (Gemma 4 26B: Google had a problem). The rest of the app keeps working.
- error in colombo_care/K02: AIUnavailable: No AI model could take this right now (Gemma 4 26B: answer didn't fit the expected form). The rest of the app keeps working.
- error in colombo_care/K03: AIUnavailable: No AI model could take this right now (Gemma 4 26B: Google had a problem). The rest of the app keeps working.
- error in colombo_care/K04: AIUnavailable: No AI model could take this right now (Gemma 4 26B: answer didn't fit the expected form). The rest of the app keeps working.
- error in jaffna/J01: AIUnavailable: No AI model could take this right now (Gemma 4 26B: answer didn't fit the expected form). The rest of the app keeps working.
- error in jaffna/J02: AIUnavailable: No AI model could take this right now (Gemma 4 26B: answer didn't fit the expected form). The rest of the app keeps working.
- error in jaffna/J03: AIUnavailable: No AI model could take this right now (Gemma 4 26B: Google had a problem). The rest of the app keeps working.
- error in perera/S01: AIUnavailable: No AI model could take this right now (Gemma 4 26B: Google had a problem). The rest of the app keeps working.
- error in perera/S02: AIUnavailable: No AI model could take this right now (Gemma 4 26B: answer didn't fit the expected form). The rest of the app keeps working.
- error in perera/S03: AIUnavailable: No AI model could take this right now (Gemma 4 26B: answer didn't fit the expected form). The rest of the app keeps working.
- error in perera/S04: AIUnavailable: No AI model could take this right now (Gemma 4 26B: Google had a problem). The rest of the app keeps working.
- error in perera/S06: AIUnavailable: No AI model could take this right now (Gemma 4 26B: Google had a problem). The rest of the app keeps working.
- error in perera/S07: AIUnavailable: No AI model could take this right now (Gemma 4 26B: Google had a problem). The rest of the app keeps working.
- error in perera/S09: AIUnavailable: No AI model could take this right now (Gemma 4 26B: took longer than 90 s). The rest of the app keeps working.
- error in perera/S10: AIUnavailable: No AI model could take this right now (Gemma 4 26B: slow right now). The rest of the app keeps working.
- error in perera/S11: AIUnavailable: No AI model could take this right now (Gemma 4 26B: slow right now). The rest of the app keeps working.
- error in perera/S12: AIUnavailable: No AI model could take this right now (Gemma 4 26B: slow right now). The rest of the app keeps working.
- error in perera/S13: AIUnavailable: No AI model could take this right now (Gemma 4 26B: slow right now). The rest of the app keeps working.

✓ meets the target, ✗ misses it. A miss is reported as it is; the household reviews every fact before it is used.
This file is generated by `python -m evals.live_models`.
