#!/usr/bin/env bash
# Build the container with Cloud Build and deploy it to Cloud Run. Run setup.sh first.
#
#   bash infra/deploy.sh
#
# Prints the service URL at the end and checks /api/health.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f infra/config.sh ] && source infra/config.sh

: "${PROJECT_ID:?Set PROJECT_ID (see infra/config.sh.example)}"
REGION="${REGION:-asia-south1}"
SERVICE="${SERVICE:-if-i-disappear}"
SA_NAME="${SA_NAME:-iid-runtime}"
BUCKET="${BUCKET:-${PROJECT_ID}-iid-uploads}"
REPO="${REPO:-iid}"
AUTH_MODE="${AUTH_MODE:-session}"
SA="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
TAG="$(date -u +%Y%m%d-%H%M%S)"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE}:${TAG}"

echo "== Building $IMAGE"
gcloud builds submit --project "$PROJECT_ID" --config infra/cloudbuild.yaml \
  --substitutions "_IMAGE=${IMAGE},_VITE_FIREBASE_API_KEY=${VITE_FIREBASE_API_KEY:-},_VITE_FIREBASE_AUTH_DOMAIN=${VITE_FIREBASE_AUTH_DOMAIN:-},_VITE_FIREBASE_PROJECT_ID=${VITE_FIREBASE_PROJECT_ID:-},_VITE_FIREBASE_APP_ID=${VITE_FIREBASE_APP_ID:-}" \
  .

SECRETS="SESSION_SECRET=session-secret:latest"
if gcloud secrets describe gemini-api-key --project "$PROJECT_ID" >/dev/null 2>&1; then
  SECRETS="${SECRETS},GEMINI_API_KEY=gemini-api-key:latest"
  echo "== Gemini key found: live AI on"
else
  echo "== No gemini-api-key secret: deploying in offline demo mode"
fi

ENV_VARS="APP_ENV=prod,STORE=firestore,UPLOAD_BUCKET=${BUCKET},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},AUTH_MODE=${AUTH_MODE}"
ENV_VARS="${ENV_VARS},QUOTA_TIER=${QUOTA_TIER:-free},AI_CALLS_PER_VISITOR=${AI_CALLS_PER_VISITOR:-40}"
echo "== QUOTA_TIER=${QUOTA_TIER:-free}, AI_CALLS_PER_VISITOR=${AI_CALLS_PER_VISITOR:-40}"
# Optional model settings from infra/config.sh. Chains are comma-separated, so they go
# through gcloud's alternative delimiter (^@^) instead of the plain list.
EXTRA=""
for var in MODEL_LIVE MODEL_REASON AI_CHAIN_LISTENER AI_CHAIN_READER AI_CHAIN_EXTRACTOR AI_CHAIN_CHALLENGER AI_CHAIN_GRADER QUOTA_LIMITS; do
  if [ -n "${!var:-}" ]; then EXTRA="${EXTRA}@${var}=${!var}"; echo "== ${var}=${!var}"; fi
done
[ -n "$EXTRA" ] && ENV_VARS="^@^${ENV_VARS//,/@}${EXTRA}"

echo "== Deploying Cloud Run service $SERVICE in $REGION"
# --no-cpu-throttling keeps CPU on after a response, so analysis jobs started by a
# request can finish in the background while the browser polls for them.
gcloud run deploy "$SERVICE" \
  --project "$PROJECT_ID" --region "$REGION" --image "$IMAGE" \
  --service-account "$SA" --allow-unauthenticated \
  --set-env-vars "$ENV_VARS" --set-secrets "$SECRETS" \
  --cpu 1 --memory 1Gi --concurrency 40 --timeout 300 \
  --min-instances "${MIN_INSTANCES:-1}" --max-instances "${MAX_INSTANCES:-1}" \
  --no-cpu-throttling --execution-environment gen2 --quiet

URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format 'value(status.url)')"
gcloud run services update "$SERVICE" --project "$PROJECT_ID" --region "$REGION" \
  --update-env-vars "ALLOWED_ORIGINS=${URL},PUBLIC_BASE_URL=${URL}" --quiet >/dev/null

echo "== Checking $URL/api/health"
for i in 1 2 3 4 5 6; do
  if curl -fsS "$URL/api/health"; then echo; break; fi
  sleep 5
done
echo
echo "Deployed: $URL"
echo "Demo:     $URL/demo"
echo "Evals:    $URL/evals"
