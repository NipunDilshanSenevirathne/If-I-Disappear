"""Signed visitor sessions (AUTH_MODE=session)."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app import config


@pytest.fixture()
def session_app(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "session")
    monkeypatch.setenv("SESSION_SECRET", "test-secret-please-change")
    monkeypatch.setenv("AI_MODE", "fixture")
    monkeypatch.setenv("STORE", "memory")
    config.get_settings.cache_clear()
    from app.main import create_app

    yield create_app()
    config.get_settings.cache_clear()


def test_sessions_are_private_and_unforgeable(session_app):
    async def flow():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=session_app), base_url="http://test") as c:
            assert (await c.post("/api/demo", json={})).status_code == 401
            a = (await c.post("/api/session")).json()
            b = (await c.post("/api/session")).json()
            assert a["uid"] != b["uid"] and a["uid"].startswith("v-")
            ha = {"Authorization": f"Bearer {a['token']}"}
            hb = {"Authorization": f"Bearer {b['token']}"}
            h = (await c.post("/api/demo", json={}, headers=ha)).json()
            assert (await c.get(f"/api/households/{h['id']}", headers=ha)).status_code == 200
            assert (await c.get(f"/api/households/{h['id']}", headers=hb)).status_code == 403
            # a forged token for A's id, signed with the wrong key, is refused
            uid, issued, _ = a["token"].rsplit(".", 2)
            forged = {"Authorization": f"Bearer {uid}.{issued}.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}
            assert (await c.get(f"/api/households/{h['id']}", headers=forged)).status_code == 401
            # the dev header means nothing in this mode
            assert (await c.get(f"/api/households/{h['id']}", headers={"X-Dev-User": a["uid"]})).status_code == 401
            # an old token has expired
            old = f"{uid}.{int(issued) - 40 * 86400}"
            from app.auth import _sign

            expired = {"Authorization": f"Bearer {old}.{_sign(old)}"}
            assert (await c.get(f"/api/households/{h['id']}", headers=expired)).status_code == 401
            assert (await c.get("/api/config")).json()["auth"] == "session"

    asyncio.run(flow())
