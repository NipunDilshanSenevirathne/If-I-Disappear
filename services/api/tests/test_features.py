"""Explore (what if), adding by hand, scope, handover links, history and the AI meter."""

from __future__ import annotations

import asyncio
import os
import tempfile

os.environ.setdefault("AI_MODE", "fixture")
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="iid-test-"))
os.environ.setdefault("STORE", "memory")
os.environ.setdefault("AUTH_MODE", "dev")

import httpx  # noqa: E402

from app.main import app  # noqa: E402

ME = {"X-Dev-User": "feature-tester"}
OTHER = {"X-Dev-User": "stranger"}


def run(coro):
    return asyncio.run(coro)


def client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def states(h: dict) -> dict[str, str]:
    return {r["id"]: r["state"] for r in h["analysis"]["result"]["responsibilities"]}


def test_explore_changes_nothing_and_shows_what_would_change():
    async def flow():
        async with client() as c:
            h = (await c.post("/api/demo", json={"reset": True}, headers=ME)).json()
            hid = h["id"]
            opts = (await c.get(f"/api/households/{hid}/explore", headers=ME)).json()
            assert {p["id"] for p in opts["people"]} == {"sunil", "kamala"}  # adults who stay; not Nirmala, not the children
            assert any(t["id"] == "sunil_phone" and t["kind"] == "handset" for t in opts["things"])
            assert opts["assumptions"] and opts["days"] == 90

            # Sunil away too: nothing that relies on him can be ready
            r = await c.post(f"/api/households/{hid}/explore", json={"also_away": ["sunil"]}, headers=ME)
            assert r.status_code == 200, r.text
            out = r.json()
            assert out["changes"] == ["Sunil is away too"]
            assert out["after"]["ready"] < out["before"]["ready"]
            gas = next(x for x in out["responsibilities"] if x["id"] == "r_gas")
            assert gas["before"] == "prepared" and gas["after"] != "prepared" and gas["worse"]

            # lifting the household's own decision ("this number stops") can only help
            lift = [a["id"] for a in opts["assumptions"]]
            out2 = (await c.post(f"/api/households/{hid}/explore", json={"keep_using": lift}, headers=ME)).json()
            assert out2["worse"] == 0

            # a shorter absence (the clinic dates still fall inside it)
            out3 = (await c.post(f"/api/households/{hid}/explore", json={"days": 14}, headers=ME)).json()
            assert out3["scenario"]["days"] == 14

            # the household itself is unchanged
            again = (await c.get(f"/api/households/{hid}", headers=ME)).json()
            assert again["rev"] == h["rev"] and states(again) == states(h)

            bad = await c.post(f"/api/households/{hid}/explore", json={"also_away": ["nobody"]}, headers=ME)
            assert bad.status_code == 400
            assert (await c.post(f"/api/households/{hid}/explore", json={}, headers=OTHER)).status_code == 403

    run(flow())


def _new_household(c):
    return c.post(
        "/api/households",
        json={
            "name": "Test household",
            "leaver_name": "Amara",
            "departure": "2026-11-01",
            "horizon_days": 60,
            "people": [{"name": "Ravi", "role": "backup", "minor": False}, {"name": "Nila", "role": "household", "minor": True}],
        },
        headers=ME,
    )


def test_adding_responsibilities_by_hand():
    async def flow():
        async with client() as c:
            h = (await _new_household(c)).json()
            hid = h["id"]
            assert h["analysis"]["result"]["summary"]["total"] == 0
            assert len(h["history"]) == 1

            # only Amara has the water bill: Ravi can't pay it while she's away
            r = await c.post(
                f"/api/households/{hid}/responsibilities",
                json={
                    "label": "Pay the water bill",
                    "category": "money",
                    "freq": "monthly",
                    "monthday": 15,
                    "taker": "ravi",
                    "agreed": "yes",
                    "importance": 2,
                    "needs": [{"name": "the water bill", "kind": "document", "held_by": "leaver"}],
                },
                headers=ME,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            rid = body["added"]["responsibility"]
            h = body["household"]
            assert states(h)[rid] == "blocked"
            assert any(f["kind"] == "held" or "held" in f["id"] for f in h["analysis"]["findings"])
            typed = next(s for s in h["sources"] if s["id"] == body["added"]["source"])
            assert typed["title"] == "Typed in: Pay the water bill"
            for claim in (c2 for c2 in h["claims"] if c2["id"] in body["added"]["claims"]):
                assert claim["review"] == "accepted" and claim["evidence"][0]["quote"] in typed["text"]

            # Ravi already has the gas shop's number: the route works, he just hasn't seen the steps
            r = await c.post(
                f"/api/households/{hid}/responsibilities",
                json={
                    "label": "Order the gas cylinder",
                    "freq": "monthly",
                    "monthday": 3,
                    "taker": "ravi",
                    "agreed": "yes",
                    "importance": 1,
                    "needs": [{"name": "the gas shop's number", "kind": "contact", "held_by": "leaver", "taker_has_it": True}],
                },
                headers=ME,
            )
            gas = r.json()["added"]["responsibility"]
            assert states(r.json()["household"])[gas] == "needs_handover"

            # nothing listed as needed: we honestly don't know yet
            r = await c.post(
                f"/api/households/{hid}/responsibilities",
                json={"label": "Water the garden", "freq": "weekly", "weekdays": ["SA"], "taker": "ravi", "agreed": "unsure"},
                headers=ME,
            )
            garden = r.json()["added"]["responsibility"]
            h = r.json()["household"]
            assert states(h)[garden] == "needs_confirmation"
            assert h["analysis"]["result"]["summary"]["total"] == 3
            assert len(h["history"]) >= 3

            # a child can't be the person taking over
            r = await c.post(
                f"/api/households/{hid}/responsibilities", json={"label": "Feed the cat", "taker": "nila", "freq": "ongoing"}, headers=ME
            )
            assert r.status_code == 400

            # leave one out of this plan: the count says so
            h = (await c.post(f"/api/households/{hid}/scope", json={"responsibility": garden, "include": False}, headers=ME)).json()
            assert h["settings"]["in_scope"] is not None and garden not in h["settings"]["in_scope"]
            assert h["analysis"]["result"]["summary"]["total"] == 2
            h = (await c.post(f"/api/households/{hid}/scope", json={"responsibility": garden, "include": True}, headers=ME)).json()
            assert h["settings"]["in_scope"] is None and h["analysis"]["result"]["summary"]["total"] == 3

    run(flow())


def test_handover_link_for_the_person_staying():
    async def flow():
        async with client() as c:
            h = (await c.post("/api/demo", json={"reset": True}, headers=ME)).json()
            hid = h["id"]
            r = await c.post(
                f"/api/households/{hid}/shares", json={"person": "sunil", "responsibilities": ["r_clinic", "r_gas"]}, headers=ME
            )
            assert r.status_code == 200, r.text
            made = r.json()
            token = made["token"]
            assert made["path"] == f"/handover#{token}"
            # the token is never stored or listed
            listed = (await c.get(f"/api/households/{hid}/shares", headers=ME)).json()
            assert listed[0]["person_name"] == "Sunil" and token not in str(listed)
            assert token not in str((await c.get(f"/api/households/{hid}", headers=ME)).json())

            # Sunil opens it: only his card entries and steps
            view = (await c.post("/api/handover/open", json={"token": token})).json()
            assert view["person_name"] == "Sunil" and view["leaver_name"] == "Nirmala"
            assert {i["responsibility"] for i in view["card"]["items"]} == {"r_clinic", "r_gas"}
            assert view["card"]["no_secrets"]
            assert "sources" not in view and "claims" not in view
            clinic = next(p for p in view["practice"] if p["responsibility"] == "r_clinic")
            assert clinic["steps"] and clinic["scenario"]

            # he practises on his phone; the household sees the attempt
            r = await c.post(
                "/api/handover/practice",
                json={
                    "token": token,
                    "responsibility": "r_clinic",
                    "transcript": "I check the date in the clinic book. I take the clinic book and the medicine list from the top "
                    "drawer of the steel cupboard. We leave before seven to get a number. We collect the tablets at the "
                    "pharmacy and I write the next date on the calendar.",
                },
            )
            assert r.status_code == 200, r.text
            assert r.json()["attempt"]["result"] == "unassisted"
            h = (await c.get(f"/api/households/{hid}", headers=ME)).json()
            assert any(a["person"] == "sunil" and a["responsibility"] == "r_clinic" for a in h["attempts"])

            # a link can't reach what it doesn't cover
            r = await c.post("/api/handover/practice", json={"token": token, "responsibility": "r_insurance", "transcript": "x"})
            assert r.status_code == 403

            # revoked: gone
            await c.delete(f"/api/households/{hid}/shares/{made['id']}", headers=ME)
            assert (await c.post("/api/handover/open", json={"token": token})).status_code == 404
            assert (await c.post("/api/handover/open", json={"token": "x" * 32})).status_code == 404

            # children and the person leaving can't get a link
            bad = await c.post(f"/api/households/{hid}/shares", json={"person": "tharushi", "responsibilities": ["r_clinic"]}, headers=ME)
            assert bad.status_code == 400
            bad = await c.post(f"/api/households/{hid}/shares", json={"person": "nirmala", "responsibilities": ["r_clinic"]}, headers=ME)
            assert bad.status_code == 400

    run(flow())


def test_history_and_ai_meter():
    async def flow():
        async with client() as c:
            h = (await c.post("/api/demo", json={"reset": True}, headers=ME)).json()
            hid = h["id"]
            assert [p["ready"] for p in h["history"]] == [1]
            h = (await c.post(f"/api/demo/{hid}/stage", json={"stage": "after_handover"}, headers=ME)).json()
            assert [p["ready"] for p in h["history"]] == [1, 6]
            assert h["history"][-1]["action"] == "demo.week_later"
            h = (await c.post(f"/api/demo/{hid}/stage", json={"stage": "capture"}, headers=ME)).json()
            assert [p["ready"] for p in h["history"]] == [1]  # a reset starts the story again

            usage = (await c.get("/api/ai/usage", headers=ME)).json()
            assert usage["mode"] == "fixture" and usage["tier"] == "free"
            labels = {m["label"] for m in usage["models"]}
            assert {"Gemini 3.8 Flash", "Gemini 3.5 Flash-Lite", "Gemma 4 31B"} <= labels
            flash = next(m for m in usage["models"] if m["model"] == "gemini-3.8-flash")
            assert flash["limit_today"] == 20 and flash["limit_per_minute"] == 5
            assert usage["resets_at"] and usage["chains"]["challenger"][0]["model"] == "gemini-3.8-flash"
            cfg = (await c.get("/api/config")).json()
            assert cfg["quota_tier"] == "free" and "languages" not in cfg

    run(flow())
