# Live browser flows

Generated from `apps/web/scripts/live-browser.mjs` (results.json) on 2026-10-13, against the app running locally in live mode (free Gemini key, memory store), in Chromium with a fake microphone playing synthetic voice recordings.

**9 of 9 flows passed.**

| Flow | Result | Time | What the page showed |
|---|---|---:|---|
| ai-pill-live | pass | 0.1 s | Free AI · 14633 left today |
| capture-photo-sample | pass | 8.1 s | Found 3 new facts and 6 facts you already had. models: Gemini 3.5 Flash-Lite |
| review-facts-with-quotes | pass | 0.7 s | 3 facts on the page, 3 quote slips |
| check-again-with-ai | pass | 9.9 s | models on the page: Gemini 3.5 Flash-Lite, Gemini 3.8 Flash, Gemini 6.3 s |
| practise-typed-graded-by-gemini | pass | 1.9 s | vague: Not yet Checked by Gemini 3.5 Flash-Lite / complete: Explained without help Checked by Gemini 3.5 Flash-Lite |
| handover-link-practice | pass | 3.0 s | Explained without help Checked by Gemini 3.5 Flash-Lite |
| ai-allowance-after | pass | 1.2 s | Runs on the free Gemini tier Live · resets at 12:30 Gemini 3.8 Flash 1 of 19 today 0/5 this minute used up for today Gemini 3.5 Flash-Lite 18 of 475 today 3/15 this minute Gemini 3.1 Flash-Lite 0 of 475 today 0/15 this minute Gemma 4 31B 0 of 13680 today 0/30  |
| voice-note-recorded-and-read | pass | 40.9 s | Found 3 new facts and 5 facts you already had. transcript: Hi, it's Nirmala. A few things for while I'm in Japan. Achi's clinic is every second Thursday at the district hospital and you have to leave by 7:00 in the morning to get a number. Her clinic book and  |
| spoken-practice-gemini-live | pass | 40.2 s | Explained without help Checked by Gemini 3.5 Flash-Lite / heard: Sunil Say in a relaxed natural voice like a husband explaining a chore. Sunil The electricity bill comes on paper every month and I have to pay it by the 10th. I take the bill and the cash to the |

Note on the last flow: the synthetic recording played into the fake microphone starts with the
text-to-speech tool's own style instruction ("Say in a relaxed natural voice…"), so the
practice partner heard that too. It is in the transcript above; the grade was still decided on
Sunil's own words.

This file is generated from the script's output. Run `make live-browser` against a live server to refresh it.
