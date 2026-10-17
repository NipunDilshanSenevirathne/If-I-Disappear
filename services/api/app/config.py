"""Runtime settings, read once from the environment.

AI_MODE
  live     Google models do the listening, reading, extracting, reviewing and
           grading (needs GEMINI_API_KEY, or Vertex AI credentials). Every call
           goes through the model router (app/ai/router.py), which keeps the app
           inside the free tier and falls back between models.
  fixture  No model calls. The same ADK workflows run with a replay model that
           returns the reviewed sample data, and the interface says so. Used for
           tests and offline development.
The default is live when a key or Vertex project is configured, otherwise fixture.

Free tier settings (see docs/FREE_TIER.md)
  QUOTA_TIER            free (default): count requests against the free-tier limits
                        in app/ai/quota.py; paid: count but never refuse
  QUOTA_LIMITS          JSON overrides, e.g. {"gemini-3.8-flash": {"rpm": 5, "rpd": 20}}
  QUOTA_RESERVE         share of each daily allowance to leave unused (default 0.05)
  AI_CHAIN_<ROLE>       model chain for a step, best first, e.g.
                        AI_CHAIN_EXTRACTOR="gemini-3.8-flash:keep=8, gemini-3.5-flash-lite"
  AI_CALLS_PER_VISITOR  model calls one visitor may cause per day (0 = no limit)
  AI_MAX_WAIT           seconds to wait for a per-minute slot before trying the next model
  AI_TIMEOUT            seconds before a single model call is abandoned
  AI_TRY_TIMEOUT        a shorter limit for a model when another one in the line could
                        still take the request (a model that is slow today is skipped
                        for two minutes)
  MODEL_LIVE            the spoken-practice model (Live API)
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

API_ROOT = Path(__file__).resolve().parents[1]
ROLES = ("listener", "reader", "extractor", "challenger", "grader")


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


class Settings(BaseModel):
    env: str = "dev"
    ai_mode: str = "fixture"
    gemini_api_key: str | None = None
    use_vertex: bool = False
    project: str | None = None
    location: str = "global"
    model_live: str = "gemini-3.8-live"
    model_override: str | None = None  # MODEL_REASON (older setting): one model first in every chain
    quota_tier: str = "free"  # free | paid
    quota_limits: str | None = None
    quota_reserve: float = 0.05
    ai_chains: dict[str, str] = {}
    ai_calls_per_visitor: int = 0
    ai_max_wait: float = 20.0
    ai_timeout: float = 90.0
    ai_try_timeout: float = 45.0
    store: str = "memory"  # memory | firestore
    bucket: str | None = None  # Cloud Storage bucket for uploads (else local disk)
    data_dir: Path = API_ROOT / ".data"
    auth: str = "dev"  # dev | session | firebase
    session_secret: str | None = None  # signs visitor sessions (AUTH_MODE=session)
    session_days: int = 30
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    demo_household: str = "perera"
    max_upload_mb: int = 15
    rate_per_minute: int = 30
    live_token_minutes: int = 30
    static_dir: Path | None = None  # serve the built web app from the API (single-service deploy)
    public_base_url: str | None = None

    @property
    def live(self) -> bool:
        return self.ai_mode == "live"


@lru_cache
def get_settings() -> Settings:
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    use_vertex = _bool("GOOGLE_GENAI_USE_VERTEXAI")
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    default_mode = "live" if (key or (use_vertex and project)) else "fixture"
    origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
    static = os.getenv("STATIC_DIR")
    chains = {role: os.environ[f"AI_CHAIN_{role.upper()}"] for role in ROLES if os.getenv(f"AI_CHAIN_{role.upper()}")}
    return Settings(
        env=os.getenv("APP_ENV", "dev"),
        ai_mode=os.getenv("AI_MODE", default_mode),
        gemini_api_key=key,
        use_vertex=use_vertex,
        project=project,
        location=os.getenv("GOOGLE_CLOUD_LOCATION", "global"),
        model_live=os.getenv("MODEL_LIVE") or "gemini-3.8-live",
        model_override=os.getenv("MODEL_REASON") or None,
        quota_tier=(os.getenv("QUOTA_TIER") or "free").lower(),
        quota_limits=os.getenv("QUOTA_LIMITS") or None,
        quota_reserve=float(os.getenv("QUOTA_RESERVE", "0.05")),
        ai_chains=chains,
        ai_calls_per_visitor=int(os.getenv("AI_CALLS_PER_VISITOR", "0")),
        ai_max_wait=float(os.getenv("AI_MAX_WAIT", "20")),
        ai_timeout=float(os.getenv("AI_TIMEOUT", "90")),
        ai_try_timeout=float(os.getenv("AI_TRY_TIMEOUT", "45")),
        store=os.getenv("STORE", "memory"),
        bucket=os.getenv("UPLOAD_BUCKET") or None,
        data_dir=Path(os.getenv("DATA_DIR", str(API_ROOT / ".data"))),
        auth=os.getenv("AUTH_MODE", "dev"),
        session_secret=os.getenv("SESSION_SECRET") or None,
        session_days=int(os.getenv("SESSION_DAYS", "30")),
        allowed_origins=origins or ["http://localhost:5173", "http://127.0.0.1:5173"],
        demo_household=os.getenv("DEMO_HOUSEHOLD", "perera"),
        max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "15")),
        rate_per_minute=int(os.getenv("RATE_PER_MINUTE", "30")),
        live_token_minutes=int(os.getenv("LIVE_TOKEN_MINUTES", "30")),
        static_dir=Path(static) if static else None,
        public_base_url=os.getenv("PUBLIC_BASE_URL") or None,
    )
