#!/usr/bin/env bash
# One-time setup of a Google Cloud project for If I Disappear. Safe to run again.
#
#   cp infra/config.sh.example infra/config.sh   # edit PROJECT_ID (and GEMINI_API_KEY)
#   bash infra/setup.sh
#
# Creates: the APIs, an Artifact Registry repository, a Firestore database (Native
# mode), a private upload bucket that deletes files after 30 days, a runtime service
# account with only the roles it needs, and two secrets (Gemini key, session key).
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f infra/config.sh ] && source infra/config.sh

: "${PROJECT_ID:?Set PROJECT_ID (see infra/config.sh.example)}"
REGION="${REGION:-asia-south1}"
SA_NAME="${SA_NAME:-iid-runtime}"
BUCKET="${BUCKET:-${PROJECT_ID}-iid-uploads}"
REPO="${REPO:-iid}"
SA="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

step() { printf '\n== %s\n' "$*"; }

step "Project $PROJECT_ID, region $REGION"
gcloud config set project "$PROJECT_ID" >/dev/null
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"

step "Enabling APIs (takes a minute the first time)"
# compute.googleapis.com creates the default service account that Cloud Build uses in new
# projects; nothing is created or billed by turning it on.
gcloud services enable \
  run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  firestore.googleapis.com storage.googleapis.com secretmanager.googleapis.com \
  iam.googleapis.com logging.googleapis.com compute.googleapis.com

step "Artifact Registry repository '$REPO'"
gcloud artifacts repositories describe "$REPO" --location "$REGION" >/dev/null 2>&1 ||
  gcloud artifacts repositories create "$REPO" --repository-format docker --location "$REGION" \
    --description "If I Disappear container images"

step "Firestore database (Native mode)"
gcloud firestore databases describe --database="(default)" >/dev/null 2>&1 ||
  gcloud firestore databases create --database="(default)" --location="$REGION" --type=firestore-native

step "Private upload bucket gs://$BUCKET (files deleted after 30 days)"
gcloud storage buckets describe "gs://$BUCKET" >/dev/null 2>&1 ||
  gcloud storage buckets create "gs://$BUCKET" --location="$REGION" --uniform-bucket-level-access --public-access-prevention
gcloud storage buckets update "gs://$BUCKET" --lifecycle-file=infra/bucket-lifecycle.json >/dev/null

step "Runtime service account $SA"
gcloud iam service-accounts describe "$SA" >/dev/null 2>&1 ||
  gcloud iam service-accounts create "$SA_NAME" --display-name "If I Disappear runtime"
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:$SA" \
  --role roles/datastore.user --condition=None >/dev/null
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member "serviceAccount:$SA" \
  --role roles/storage.objectAdmin >/dev/null

step "Build permissions (Cloud Build pushes the image to Artifact Registry)"
for builder in "${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" "${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"; do
  if gcloud iam service-accounts describe "$builder" >/dev/null 2>&1 || [[ "$builder" == *cloudbuild* ]]; then
    for role in roles/artifactregistry.writer roles/logging.logWriter roles/storage.objectViewer; do
      gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:$builder" \
        --role "$role" --condition=None >/dev/null 2>&1 || true
    done
  fi
done

step "Secrets"
if ! gcloud secrets describe session-secret >/dev/null 2>&1; then
  python3 -c "import secrets; print(secrets.token_urlsafe(48), end='')" |
    gcloud secrets create session-secret --data-file=- --replication-policy=automatic >/dev/null
  echo "Created session-secret (signs visitor sessions)."
fi
if ! gcloud secrets describe gemini-api-key >/dev/null 2>&1; then
  if [ -n "${GEMINI_API_KEY:-}" ]; then
    printf %s "$GEMINI_API_KEY" | gcloud secrets create gemini-api-key --data-file=- --replication-policy=automatic >/dev/null
    echo "Stored your Gemini API key as gemini-api-key."
  else
    echo "No GEMINI_API_KEY given: the app will run in offline demo mode. Add it later with:"
    echo "  printf %s 'YOUR_KEY' | gcloud secrets create gemini-api-key --data-file=-"
  fi
fi
for secret in session-secret gemini-api-key; do
  if gcloud secrets describe "$secret" >/dev/null 2>&1; then
    gcloud secrets add-iam-policy-binding "$secret" --member "serviceAccount:$SA" \
      --role roles/secretmanager.secretAccessor >/dev/null
  fi
done

step "Done. Next: bash infra/deploy.sh"
