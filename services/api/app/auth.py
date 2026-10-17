"""Who is calling.

Three modes (AUTH_MODE):

session   (default for a deployment) Each visitor gets a private, signed session:
          the browser calls POST /api/session once and sends the token back as
          `Authorization: Bearer <token>`. Tokens are HMAC-SHA256 signed with
          SESSION_SECRET, so a visitor id can't be guessed or forged, and no
          sign-in screen stands between a judge and the demo.
firebase  The browser signs in with Firebase Auth (anonymous sign-in, Google
          sign-in optional) and sends the Firebase ID token; we verify it with the
          Admin SDK. Use this when households should follow a person across devices.
dev       Local development only: `X-Dev-User` names the user.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import re
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import HTTPException, Request

from .config import get_settings

_firebase_ready = False


@dataclass
class User:
    uid: str
    anonymous: bool = True
    name: str | None = None


def _init_firebase() -> None:
    global _firebase_ready
    if _firebase_ready:
        return
    import firebase_admin

    if not firebase_admin._apps:
        s = get_settings()
        firebase_admin.initialize_app(options={"projectId": s.project} if s.project else None)
    _firebase_ready = True


# ---------------------------------------------------------------------- signed sessions


def _secret() -> bytes:
    s = get_settings()
    if not s.session_secret:
        raise HTTPException(500, "Sessions aren't configured on this server (SESSION_SECRET is missing).")
    return s.session_secret.encode()


def _sign(payload: str) -> str:
    mac = hmac.new(_secret(), payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode().rstrip("=")


def issue_session() -> dict:
    uid = f"v-{secrets.token_urlsafe(12)}"
    issued = int(time.time())
    payload = f"{uid}.{issued}"
    return {"token": f"{payload}.{_sign(payload)}", "uid": uid, "expires_in_days": get_settings().session_days}


def verify_session(token: str) -> str:
    try:
        uid, issued, mac = token.rsplit(".", 2)
        age_days = (time.time() - int(issued)) / 86400
    except ValueError as exc:
        raise HTTPException(401, "Your session isn't valid. Reload the page.") from exc
    if not hmac.compare_digest(mac, _sign(f"{uid}.{issued}")):
        raise HTTPException(401, "Your session isn't valid. Reload the page.")
    if age_days > get_settings().session_days or age_days < -1:
        raise HTTPException(401, "Your session has expired. Reload the page.")
    if not re.fullmatch(r"v-[A-Za-z0-9_-]{8,40}", uid):
        raise HTTPException(401, "Your session isn't valid. Reload the page.")
    return uid


async def current_user(request: Request) -> User:
    s = get_settings()
    if s.auth == "session":
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise HTTPException(401, "Start a session to continue.")
        return User(uid=verify_session(header.removeprefix("Bearer ").strip()), anonymous=True)
    if s.auth == "firebase":
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise HTTPException(401, "Sign in to continue.")
        token = header.removeprefix("Bearer ").strip()
        _init_firebase()
        from firebase_admin import auth as fb_auth

        try:
            claims = await asyncio.to_thread(fb_auth.verify_id_token, token)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(401, "Your sign-in has expired. Reload the page.") from exc
        provider = (claims.get("firebase") or {}).get("sign_in_provider", "")
        return User(uid=claims["uid"], anonymous=provider == "anonymous", name=claims.get("name"))
    uid = request.headers.get("X-Dev-User", "dev-user")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", uid):
        raise HTTPException(400, "Bad user id.")
    return User(uid=uid, anonymous=False, name=uid)


# ---------------------------------------------------------------------- rate limits

_hits: dict[tuple[str, str], deque] = defaultdict(deque)


def limit_ip(request: Request, bucket: str, per_minute: int) -> None:
    """The same sliding window, keyed by client address (for calls made before there is a user)."""
    # the last entry is the address the platform saw; earlier ones can be set by the client
    forwarded = [x.strip() for x in request.headers.get("X-Forwarded-For", "").split(",") if x.strip()]
    ip = forwarded[-1] if forwarded else (request.client.host if request.client else "unknown")
    limit(User(uid=f"ip:{ip}"), bucket, per_minute)


def limit(user: User, bucket: str, per_minute: int | None = None) -> None:
    """A simple per-user sliding window for the expensive endpoints (per instance)."""
    cap = per_minute or get_settings().rate_per_minute
    key = (user.uid, bucket)
    now = time.monotonic()
    if len(_hits) > 20000:  # forget idle callers so the table can't grow without bound
        for k in [k for k, q in _hits.items() if not q or now - q[-1] > 60]:
            del _hits[k]
    q = _hits[key]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= cap:
        raise HTTPException(429, "That's a lot of requests in a minute. Wait a moment and try again.")
    q.append(now)
