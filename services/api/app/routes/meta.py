"""Health, public configuration and the evaluation report."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from ..ai.quota import label
from ..ai.router import chain_for, usage_snapshot
from ..auth import User, current_user, issue_session, limit_ip
from ..config import get_settings
from ..engine.model import ENGINE_VERSION, POLICY_VERSION

router = APIRouter(prefix="/api", tags=["meta"])
VERSION = "2.1.0"


def _report_path() -> Path:
    """evals/reports/latest.json: EVALS_REPORT if set, else the repository copy
    (found by walking up from this file), else next to the app in a container."""
    env = os.getenv("EVALS_REPORT")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "evals" / "reports" / "latest.json"
        if candidate.exists():
            return candidate
    return here.parents[2] / "evals" / "reports" / "latest.json"


REPORT = _report_path()


@router.get("/health")
async def health():
    s = get_settings()
    return {
        "ok": True,
        "version": VERSION,
        "engine": ENGINE_VERSION,
        "policy": POLICY_VERSION,
        "ai_mode": s.ai_mode,
        "quota_tier": s.quota_tier,
        "store": s.store,
    }


@router.get("/config")
async def public_config():
    s = get_settings()
    return {
        "version": VERSION,
        "ai_mode": s.ai_mode,
        "live_voice": s.live,
        "models": {
            "extract": label(chain_for("extractor")[0].model),
            "review": label(chain_for("challenger")[0].model),
            "live": label(s.model_live),
        }
        if s.live
        else None,
        "quota_tier": s.quota_tier,
        "auth": s.auth,
        "max_upload_mb": s.max_upload_mb,
    }


@router.post("/session")
async def start_session(request: Request):
    """A private, signed visitor session (AUTH_MODE=session). Other modes don't use it."""
    if get_settings().auth != "session":
        raise HTTPException(404, "Sessions aren't used on this server.")
    limit_ip(request, "session", 20)
    return issue_session()


@router.get("/ai/usage")
async def ai_usage(user: User = Depends(current_user)):
    """Today's free-tier usage per model, and this visitor's own allowance (for the live meter)."""
    return usage_snapshot(user.uid)


@router.get("/evals")
async def evals():
    """The latest evaluation report produced by `python -m evals.run` (never hand-written)."""
    if not REPORT.exists():
        return {"available": False, "note": "No evaluation report yet. Run `make eval` to produce one."}
    return {"available": True, **json.loads(REPORT.read_text(encoding="utf-8"))}
