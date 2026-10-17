# How to run If I Disappear

Three ways, from quickest to complete:

1. **On your computer, offline** (no key, five minutes): the full app with the sample
   households; AI steps replay reviewed sample data and say so.
2. **On your computer, with Gemini**: add a free Gemini API key; listening, reading,
   extraction, the AI reviewer, grading and spoken practice run live, through the free-tier
   model router ([docs/FREE_TIER.md](docs/FREE_TIER.md)).
3. **On Google Cloud**: one Cloud Run service with Firestore, Cloud Storage and Secret
   Manager, which is what the competition needs.

---

## 0. What you need

| For | You need |
|---|---|
| Running locally | **Python 3.12 or newer** (tested on 3.13), **Node.js 22** with npm, **git**, and `make` (macOS and Linux have it; on Windows use WSL, or the manual commands below) |
| Live AI | A **Gemini API key** from [Google AI Studio](https://aistudio.google.com/apikey) |
| Deploying | A **Google Cloud project with billing**, and the **gcloud CLI** ([install](https://cloud.google.com/sdk/docs/install)) |
| Optional | Docker (to build the container locally); the Firebase CLI (only for Firebase Hosting) |

Check your versions:

```bash
python3 --version   # 3.12+
node --version      # v22.x
npm --version
```

---

## 1. Run it on your computer (offline demo)

```bash
git clone https://github.com/<you>/if-i-disappear.git
cd if-i-disappear
make setup     # creates .venv, installs the API and the web app (2–3 minutes)
make serve     # builds the web app and serves everything on http://localhost:8080
```

Open **http://localhost:8080** and choose **See a family's plan**. A short tour starts (skip it
or take it; it's in the top bar later). The pill at the top right says **Offline demo**.
Everything works: the overview and its live charts, What we found, Explore, Calendar, Plan,
practice by typing, the Continuity Card, Share and the handover link, "Jump a week ahead", the
what-if variants, the other sample households and the Evaluation page. New sources you add
can't be read offline (the app tells you so), except the eight sample documents on Capture →
**Photo or PDF**, which replay their reviewed facts. Adding a task **By hand** needs no AI.

For development with hot reload, use `make dev` instead (API on :8080, web app on
**http://localhost:5173**).

Stop with **Ctrl+C**.

### Without make (Windows PowerShell, or if you prefer)

```powershell
# terminal 1: the API
python -m venv .venv
.venv\Scripts\python -m pip install -r services\api\requirements-dev.txt
cd services\api
..\..\.venv\Scripts\uvicorn app.main:app --reload --port 8080

# terminal 2: the web app
cd apps\web
$env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD="1"; npm ci
npm run dev
```

On macOS or Linux, use `.venv/bin/...` instead of `.venv\Scripts\...`.

---

## 2. Turn on Gemini

1. Get a key at [Google AI Studio](https://aistudio.google.com/apikey).
2. Create `services/api/.env` from the example and paste the key:

   ```bash
   cp services/api/.env.example services/api/.env
   # edit services/api/.env:  GEMINI_API_KEY=your-key
   ```

3. Restart (`make serve` or `make dev`). The pill at the top right now says **Free AI · N left
   today**, and http://localhost:8080/api/health shows `"ai_mode": "live"`.

A **free key works**: the router spreads the work over Gemini 3.8 Flash, Gemini 3.5 and 3.1
Flash-Lite and Gemma 4 31B, inside each model's free limits ([docs/FREE_TIER.md](docs/FREE_TIER.md)).
With a paid key, add `QUOTA_TIER=paid`.

Try it:

- **Capture**: tick the consent box, then record a voice note, upload a photo of a document, or
  pick a sample document. Watch the steps (Listening or Reading, Finding facts, Checking every
  quote) and the model that answered each, then accept the facts on **Review facts**.
- **Overview → Check again with AI**: the full check with the Gemini reviewer; see what it did
  on **How it was worked out**.
- **Practise → the microphone**: a spoken practice partner (Gemini Live). The browser asks for
  the microphone; it works on `localhost` and on HTTPS sites.
- **The AI pill**: open it to see each model's allowance today, live.

If Google renames a model, set the lines of models in `.env` (`AI_CHAIN_EXTRACTOR=...`, see
[docs/FREE_TIER.md](docs/FREE_TIER.md#settings)) or `MODEL_LIVE`; nothing else needs to change.

> **Vertex AI instead of an API key**: set `GOOGLE_GENAI_USE_VERTEXAI=true`,
> `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION=global`, and run
> `gcloud auth application-default login`. Everything works except spoken practice, which
> needs Gemini API ephemeral tokens.

---

## 3. Tests and the evaluation report

```bash
make test        # API tests: engine, compiler, quotes, redaction, router, workflows, HTTP API (no network)
make lint        # ruff and TypeScript
make eval        # evaluation report, no model calls: evals/reports/latest.md (about 30 s)
make eval-live   # adds Gemini extraction on the benchmark sources (needs GEMINI_API_KEY; costs quota)
make serve       # in one terminal, then in another:
make smoke       # browser end-to-end test of 22 flows (needs a Chromium for Playwright)
make a11y        # accessibility check (axe-core, WCAG 2.2 AA): 16 screens, light and dark, desktop and phone
make bench       # API response times -> evals/reports/api-benchmark.md (server with AUTH_MODE=dev)
make lighthouse  # Lighthouse, phone and desktop, on four pages -> evals/reports/lighthouse.md (needs Node)
make screenshots # every screen, light and dark, desktop and phone -> docs/screenshots
make diagrams    # draw docs/diagrams/*.png from their sources
```

For `make eval-live`, export the key in your shell first
(`export GEMINI_API_KEY=...`, or `set -a; source services/api/.env; set +a`).
The report is what the app shows at `/evals`. Commit `evals/reports/latest.*` after running it
so the deployed app shows the same numbers. The copy in the repository is from the live run on
13 October 2026; `make eval` without a key rewrites it with the live checks marked "not run", so
don't commit that over it.

### With a real key: the live checks

These call Google's models, so they use free-tier allowance (about 30 to 60 requests each).
They were run on 13 October 2026; the results are in `evals/reports/`.

```bash
export GEMINI_API_KEY=...          # never commit it
make live-check                    # every model and every AI path once -> evals/reports/live-check.md
make live-check VOICE=note.wav     # the same, with your own voice note
make live-models                   # extraction quality per model on the benchmark -> live-models.md
# a server with the key in one terminal (AI_MODE=live make serve), then:
make live-browser                  # nine flows in a real browser, including Gemini Live practice
```

`make live-browser` uses Chromium's fake microphone: set `VOICE_NOTE=note.wav` and
`PRACTICE_VOICE=answer.wav` (16-bit WAV) to play your own recordings into it.
[docs/LIVE_ACCEPTANCE.md](docs/LIVE_ACCEPTANCE.md) is the checklist to do the same by hand on a
phone.

---

## 4. Run it like production, on your computer

The deployed app is one container: the API also serves the built web app.

**With Docker:**

```bash
make docker       # builds the image (web + API)
make docker-run   # http://localhost:8080 ; pass GEMINI_API_KEY in your shell to turn on live AI
```

**Without Docker:** `make serve` (add `AUTH_MODE=session SESSION_SECRET=local-test` to
`services/api/.env` to use signed visitor sessions as the container does).

---

## 5. Deploy to Google Cloud (Cloud Run)

This creates: a Cloud Run service (web + API), a Firestore database, a private upload bucket
(files deleted after 30 days), a runtime service account with only the roles it needs, and
two secrets in Secret Manager (your Gemini key and a session key).

### 5.1 Prepare

```bash
gcloud auth login
gcloud projects create YOUR-PROJECT-ID      # or use an existing project
# link billing: https://console.cloud.google.com/billing  (required for Cloud Run)
cp infra/config.sh.example infra/config.sh
```

Edit `infra/config.sh`:

```bash
export PROJECT_ID="YOUR-PROJECT-ID"
export REGION="asia-south1"        # Mumbai, closest to Sri Lanka (asia-southeast1 = Singapore)
export GEMINI_API_KEY="your-key"   # stored in Secret Manager by setup.sh; you can clear it afterwards
export AUTH_MODE="session"
export QUOTA_TIER="free"           # "paid" if your key is on a paid plan
export AI_CALLS_PER_VISITOR="40"   # a fair daily share per visitor
export MIN_INSTANCES="1"           # keep one warm while judges are looking; 0 afterwards
export MAX_INSTANCES="1"           # one instance keeps one accurate count of the free allowance
```

`infra/config.sh` is in `.gitignore`. Don't commit it.

### 5.2 One-time setup

```bash
bash infra/setup.sh
```

It enables the APIs, creates the Artifact Registry repository, Firestore (Native mode), the
bucket, the service account and the secrets, and gives Cloud Build permission to push images.
It's safe to run again.

### 5.3 Deploy

```bash
bash infra/deploy.sh
```

Cloud Build builds the container (about 4–6 minutes the first time), then Cloud Run deploys
it. At the end you'll see:

```text
Deployed: https://if-i-disappear-xxxxxxxx.asia-south1.run.app
Demo:     https://…/demo
Evals:    https://…/evals
```

Check `https://…/api/health`: it should say `"ai_mode": "live"`, `"quota_tier": "free"` and
`"store": "firestore"`.
Then open the link in a private window and go through
[docs/JUDGE_GUIDE.md](docs/JUDGE_GUIDE.md).

### 5.4 Later

- **Update**: run `bash infra/deploy.sh` again.
- **Add or change the Gemini key**:
  `printf %s 'NEW-KEY' | gcloud secrets versions add gemini-api-key --data-file=-`
  (create it with `gcloud secrets create gemini-api-key --data-file=-` if it doesn't exist),
  then grant access by re-running `bash infra/setup.sh`, and redeploy.
- **Logs**: `gcloud run services logs read if-i-disappear --region asia-south1 --limit 100`
- **Costs**: with `MIN_INSTANCES=1`, one small instance runs all the time (roughly the cost of a
  small VM). After judging: `MIN_INSTANCES=0 bash infra/deploy.sh`. Set a budget alert in the
  console either way.
- **Remove everything**: `gcloud run services delete if-i-disappear --region asia-south1`,
  delete the bucket and the secrets, or delete the project.

### 5.5 Optional: Firebase

- **Firebase Hosting in front of Cloud Run** (a `web.app` address and Firebase's CDN): add
  Firebase to the project in the [Firebase console](https://console.firebase.google.com/),
  `npm i -g firebase-tools`, `firebase login`, copy `.firebaserc.example` to `.firebaserc`
  with your project id, check the region in `firebase.json`, then
  `make build && firebase deploy --only hosting,firestore:rules`. API calls go through the
  `/api/**` rewrite to Cloud Run.
- **Firebase Auth instead of signed sessions** (households that follow a person across
  devices): enable **Anonymous** sign-in under Authentication, register a web app, put its
  config in `infra/config.sh` (`VITE_FIREBASE_*`), set `AUTH_MODE="firebase"`, and redeploy.

---

## 6. Configuration

All settings are environment variables (see `services/api/.env.example`).

| Variable | Default | Meaning |
|---|---|---|
| `GEMINI_API_KEY` | none | Turns on live AI. Without it (and without Vertex AI) the app is an offline demo. |
| `AI_MODE` | `live` with a key, else `fixture` | Force `fixture` to replay sample data even with a key. |
| `QUOTA_TIER` | `free` | `free` keeps every model inside its free limits; `paid` counts but never refuses. |
| `QUOTA_LIMITS` | none | JSON overrides of a model's limits, e.g. `{"gemini-3.8-flash": {"rpm": 10, "rpd": 250}}`. |
| `QUOTA_RESERVE` | `0.05` | Share of each daily allowance kept back as a safety margin. |
| `AI_CHAIN_LISTENER`, `AI_CHAIN_READER`, `AI_CHAIN_EXTRACTOR`, `AI_CHAIN_CHALLENGER`, `AI_CHAIN_GRADER` | see [FREE_TIER.md](docs/FREE_TIER.md) | Each job's line of models, best first, e.g. `gemini-3.5-flash-lite:keep=100, gemma-4-31b-it`. |
| `AI_CALLS_PER_VISITOR` | `0` (no limit) | AI calls per visitor per day (40 on the deployed app). |
| `AI_MAX_WAIT`, `AI_TIMEOUT` | 20, 90 | Seconds to wait for a per-minute slot; seconds before a call is given up. |
| `AI_TRY_TIMEOUT` | 45 | A shorter limit when another model could still take the request; a model that times out is skipped for two minutes. |
| `MODEL_LIVE` | `gemini-3.8-live` | The spoken practice model. |
| `MODEL_REASON` | none | Older setting: puts one model first in every line. |
| `GOOGLE_GENAI_USE_VERTEXAI`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` | off | Use Vertex AI instead of an API key. |
| `STORE` | `memory` | `firestore` in production (set by `deploy.sh`). |
| `UPLOAD_BUCKET` | none | Cloud Storage bucket for uploads; local disk without it. |
| `AUTH_MODE` | `dev` locally, `session` in the container | `dev`, `session` or `firebase`. |
| `SESSION_SECRET` | none | Signs visitor sessions; required for `session` (from Secret Manager in production). |
| `ALLOWED_ORIGINS` | localhost:5173 | CORS origins (only needed if the web app is on another origin). |
| `STATIC_DIR` | none | Serve the built web app from the API (set in the container). |
| `DEMO_HOUSEHOLD` | `perera` | The sample household opened by default. |
| `MAX_UPLOAD_MB`, `RATE_PER_MINUTE`, `LIVE_TOKEN_MINUTES` | 15, 30, 30 | Limits. |
| `VITE_FIREBASE_*` | none | Web build settings for `AUTH_MODE=firebase` only. |

---

## 7. Troubleshooting

| You see | Do this |
|---|---|
| The AI pill says **Offline demo** after adding a key | Restart the API; check `.env` is in `services/api/` and `/api/health` says `live`. In Cloud Run, check the `gemini-api-key` secret exists and redeploy. |
| "No AI model could take this right now" | Every model in that job's line is busy or used up for today. Open the AI pill to see which and when they reset (midnight Pacific time). Everything except reading new sources keeps working; add tasks by hand meanwhile. |
| "You've used this demo's AI allowance for today" | The per-visitor share (`AI_CALLS_PER_VISITOR`) is used up. Raise it, or wait until it resets. |
| `PERMISSION_DENIED` in Cloud Build | Re-run `bash infra/setup.sh` (it grants the build service accounts permission to push), wait a minute, deploy again. |
| `allUsers` can't be added / the URL asks for a Google sign-in | Your organisation blocks public Cloud Run services. Use a project outside the organisation, or ask an admin to allow it for this project. |
| Firestore errors on first deploy | Make sure `setup.sh` created the `(default)` database in Native mode: `gcloud firestore databases describe --database="(default)"`. |
| **Talk** isn't offered in Practise | Spoken practice needs live mode with a Gemini **API key** (not Vertex AI). |
| The microphone doesn't start | Allow the microphone for the site; it only works on `https://` or `localhost`. Type the explanation instead. |
| A model error mentioning the model name | Google may have renamed it: set the job's line (`AI_CHAIN_*`) or `MODEL_LIVE` to current names. |
| "Your session isn't valid. Reload the page." | The session key changed (for example after rotating `session-secret`). Reloading starts a new session; the old sample copies are left behind. |
| 429 "That's a lot of requests in a minute" | Rate limits protect the public demo; wait a minute. |
| `npm ci` tries to download browsers | Set `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` (Playwright is only used for screenshots and the smoke test). |
| Taking screenshots or running the smoke test | Run `make serve`, then `make screenshots` or `make smoke` in another terminal. Playwright needs a Chromium: set `CHROMIUM_PATH` or run `npx playwright install chromium`. |
