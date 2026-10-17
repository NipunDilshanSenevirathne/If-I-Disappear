# syntax=docker/dockerfile:1.7
# One container for Cloud Run: the FastAPI service plus the built web app
# (served from the same origin, so there is a single URL to share).
#
#   docker build -t if-i-disappear .
#   docker run -p 8080:8080 -e SESSION_SECRET=change-me if-i-disappear
#
# Build args (optional, only for AUTH_MODE=firebase): VITE_FIREBASE_API_KEY,
# VITE_FIREBASE_AUTH_DOMAIN, VITE_FIREBASE_PROJECT_ID, VITE_FIREBASE_APP_ID.

# ---------------------------------------------------------------- web build
FROM node:22-bookworm-slim AS web
WORKDIR /web
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    npm_config_fund=false \
    npm_config_audit=false
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web/ ./
ARG VITE_FIREBASE_API_KEY=""
ARG VITE_FIREBASE_AUTH_DOMAIN=""
ARG VITE_FIREBASE_PROJECT_ID=""
ARG VITE_FIREBASE_APP_ID=""
ENV VITE_FIREBASE_API_KEY=$VITE_FIREBASE_API_KEY \
    VITE_FIREBASE_AUTH_DOMAIN=$VITE_FIREBASE_AUTH_DOMAIN \
    VITE_FIREBASE_PROJECT_ID=$VITE_FIREBASE_PROJECT_ID \
    VITE_FIREBASE_APP_ID=$VITE_FIREBASE_APP_ID
RUN npm run build

# ---------------------------------------------------------------- API runtime
FROM python:3.13-slim-bookworm AS api
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY services/api/requirements.txt ./
RUN pip install -r requirements.txt
COPY services/api/app ./app
COPY services/api/fixtures ./fixtures
COPY evals/reports ./evals/reports
COPY --from=web /web/dist ./web
RUN useradd --create-home --uid 10001 app && mkdir -p /app/.data && chown -R app /app/.data
USER app
# Defaults for a deployment; Cloud Run sets PORT. Override anything with --set-env-vars.
ENV PORT=8080 \
    APP_ENV=prod \
    STATIC_DIR=/app/web \
    EVALS_REPORT=/app/evals/reports/latest.json \
    AUTH_MODE=session \
    STORE=memory \
    QUOTA_TIER=free
EXPOSE 8080
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips="*" --timeout-keep-alive 30
