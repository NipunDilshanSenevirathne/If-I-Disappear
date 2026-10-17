"""The API end to end in fixture mode (no network, no model calls)."""

from __future__ import annotations

import asyncio
import io
import os
import tempfile

os.environ.setdefault("AI_MODE", "fixture")
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="iid-test-"))  # uploads never land in the repo
os.environ.setdefault("STORE", "memory")
os.environ.setdefault("AUTH_MODE", "dev")

import httpx  # noqa: E402

from app.main import app  # noqa: E402
from app.services import jobs  # noqa: E402

ME = {"X-Dev-User": "judge-1"}
OTHER = {"X-Dev-User": "someone-else"}


def run(coro):
    return asyncio.run(coro)


async def _client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _job(c, job):
    await jobs.wait_all()
    r = await c.get(f"/api/jobs/{job['id']}", headers=ME)
    assert r.status_code == 200
    return r.json()


def test_demo_walkthrough():
    async def flow():
        async with await _client() as c:
            assert (await c.get("/api/health")).json()["ai_mode"] == "fixture"
            h = (await c.post("/api/demo", json={}, headers=ME)).json()
            hid = h["id"]
            assert h["demo"] and h["analysis"]["result"]["summary"]["sentence"] == "1 of 7 ready for this absence"
            assert len(h["variants"]) == 4

            # someone else can't see it
            assert (await c.get(f"/api/households/{hid}", headers=OTHER)).status_code == 403

            # full analysis with the (offline) AI review runs as a job
            job = (await c.post(f"/api/households/{hid}/analyze", json={}, headers=ME)).json()["job"]
            done = await _job(c, job)
            assert done["status"] == "done", done
            assert any(step["node"] == "challenger" for step in done["progress"])
            h = (await c.get(f"/api/households/{hid}", headers=ME)).json()
            assert h["analysis"]["workflow"] == "adk" and h["analysis"]["challenge"] == "offline-rules"

            # evidence for a plan step changes the state; the plan alone doesn't
            r = await c.post(
                f"/api/households/{hid}/evidence", data={"step_id": "ask:sunil:r_electricity", "kind": "AGREEMENT"}, headers=ME
            )
            assert r.status_code == 200, r.text
            states = {x["id"]: x["state"] for x in r.json()["household"]["analysis"]["result"]["responsibilities"]}
            assert states["r_electricity"] == "needs_handover"

            # practice: the explanation covers every step, no hints -> unassisted -> prepared
            r = await c.post(
                f"/api/households/{hid}/practice/r_electricity/attempts",
                json={
                    "person": "sunil",
                    "transcript": "The bill comes every month, I pay by the 10th. I take the bill and cash to the post office and keep the receipt.",
                },
                headers=ME,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["attempt"]["result"] == "unassisted"
            states = {x["id"]: x["state"] for x in body["household"]["analysis"]["result"]["responsibilities"]}
            assert states["r_electricity"] == "prepared"

            # a hint means "practised with help", which doesn't meet the standard policy
            r = await c.post(
                f"/api/households/{hid}/practice/r_van_fee/attempts",
                json={
                    "person": "sunil",
                    "transcript": "On the 5th I pay Mr Silva 6,500 in cash at the morning pickup, or call him to come in the evening.",
                    "hints_given": 1,
                },
                headers=ME,
            )
            assert r.json()["attempt"]["result"] == "practiced_with_help"

            # answer the contradiction: the newer note is right
            r = await c.post(f"/api/households/{hid}/findings/conflict:amount:r_van_fee/answer", json={"keep_claim": "C19"}, headers=ME)
            assert r.status_code == 200, r.text
            ids = {f["id"] for f in r.json()["household"]["analysis"]["findings"]}
            assert "conflict:amount:r_van_fee" not in ids

            # the card never carries secrets
            card = (await c.get(f"/api/households/{hid}/card", headers=ME)).json()
            assert card["no_secrets"] and card["items"]
            clinic = next(i for i in card["items"] if i["responsibility"] == "r_clinic")
            assert any(w["kind"] == "place" for w in clinic["where"])

            # jump a week ahead (all the evidence recorded): 6 of 7, one honest gap
            h = (await c.post(f"/api/demo/{hid}/stage", json={"stage": "after_handover"}, headers=ME)).json()
            assert h["analysis"]["result"]["summary"]["sentence"] == "6 of 7 ready for this absence"

            # a judge's "what if": keep the old number at home
            h = (await c.post(f"/api/demo/{hid}/variant", json={"variant": "keep_number"}, headers=ME)).json()
            assert h["variant"] == "keep_number"
            h = (await c.post(f"/api/demo/{hid}/stage", json={"stage": "capture"}, headers=ME)).json()
            assert "shared:nirmala_number" not in {f["id"] for f in h["analysis"]["findings"]}

            # spoken practice needs live mode
            r = await c.post(f"/api/households/{hid}/practice/r_clinic/token", json={"person": "sunil"}, headers=ME)
            assert r.status_code == 503

    run(flow())


def test_sources_and_review():
    async def flow():
        async with await _client() as c:
            h = (await c.post("/api/demo", json={"reset": True}, headers={"X-Dev-User": "judge-2"})).json()
            hid = h["id"]
            hdr = {"X-Dev-User": "judge-2"}
            # a typed note in fixture mode: secrets are removed, and we say plainly that live AI is off
            r = await c.post(
                f"/api/households/{hid}/sources",
                data={"text": "The rent is paid on the 1st. My PIN is 4821.", "title": "Rent"},
                headers=hdr,
            )
            assert r.status_code == 200, r.text
            await jobs.wait_all()
            job = (await c.get(f"/api/jobs/{r.json()['job']['id']}", headers=hdr)).json()
            assert job["status"] == "done"
            assert "Live AI is off" in job["result"]["summary"]
            h = (await c.get(f"/api/households/{hid}", headers=hdr)).json()
            src = next(s for s in h["sources"] if s["id"] == r.json()["source_id"])
            assert "4821" not in src["text"] and src["redactions"] == 1

            # re-extracting a demo source replays the reviewed claims and merges them
            r = await c.post(f"/api/households/{hid}/sources/S04/extract", headers=hdr)
            await jobs.wait_all()
            job = (await c.get(f"/api/jobs/{r.json()['job']['id']}", headers=hdr)).json()
            assert job["result"]["merged"] == 5 and job["result"]["added"] == 0

            # uploading a sample image is recognised and replayed
            from app.domain.household import household_dir

            png = household_dir("perera") / "files" / "S04.png"
            if png.exists():
                files = {"file": ("bill.png", png.read_bytes(), "image/png")}
                r = await c.post(f"/api/households/{hid}/sources", files=files, data={"title": "Bill"}, headers=hdr)
                await jobs.wait_all()
                job = (await c.get(f"/api/jobs/{r.json()['job']['id']}", headers=hdr)).json()
                assert job["status"] == "done" and job["result"]["replayed"]

            # review: reject and undo a claim
            r = await c.post(f"/api/households/{hid}/claims/C10", json={"action": "reject"}, headers=hdr)
            assert next(x for x in r.json()["claims"] if x["id"] == "C10")["review"] == "withdrawn"
            r = await c.post(f"/api/households/{hid}/claims/C10", json={"action": "accept"}, headers=hdr)
            assert next(x for x in r.json()["claims"] if x["id"] == "C10")["review"] == "accepted"

            # a bad upload type is refused
            r = await c.post(
                f"/api/households/{hid}/sources", files={"file": ("x.exe", io.BytesIO(b"MZ"), "application/x-msdownload")}, headers=hdr
            )
            assert r.status_code == 415

    run(flow())


def test_new_household_and_delete():
    async def flow():
        async with await _client() as c:
            hdr = {"X-Dev-User": "family-1"}
            r = await c.post(
                "/api/households",
                json={
                    "name": "Silva home",
                    "leaver_name": "Dilani",
                    "departure": "2026-12-01",
                    "people": [{"name": "Ruwan", "role": "backup"}, {"name": "Kavi", "minor": True}],
                },
                headers=hdr,
            )
            assert r.status_code == 200, r.text
            h = r.json()
            assert [p["name"] for p in h["people"]] == ["Dilani", "Ruwan", "Kavi"]
            assert h["analysis"]["result"]["summary"]["total"] == 0
            listing = (await c.get("/api/households", headers=hdr)).json()
            assert any(x["id"] == h["id"] for x in listing)
            assert (await c.delete(f"/api/households/{h['id']}", headers=hdr)).json() == {"deleted": h["id"]}
            assert (await c.get(f"/api/households/{h['id']}", headers=hdr)).status_code == 404

    run(flow())


def test_other_sample_households_open_as_demos():
    async def flow():
        async with await _client() as c:
            demos = (await c.get("/api/demos")).json()
            assert [d["id"] for d in demos][:1] == ["perera"]
            assert {"jaffna", "batangas", "colombo_care"} <= {d["id"] for d in demos}
            main = (await c.post("/api/demo", json={}, headers=ME)).json()
            h = (await c.post("/api/demo", json={"household": "colombo_care"}, headers=ME)).json()
            assert h["id"] != main["id"] and h["demo_source"] == "colombo_care"
            assert h["stages_available"] == ["capture"] and h["variants"] == []
            assert h["analysis"]["result"]["summary"]["sentence"] == "1 of 3 ready for this absence"
            # opening it again returns the same copy
            again = (await c.post("/api/demo", json={"household": "colombo_care"}, headers=ME)).json()
            assert again["id"] == h["id"]
            # no "week later" stage for this one
            r = await c.post(f"/api/demo/{h['id']}/stage", json={"stage": "after_handover"}, headers=ME)
            assert r.status_code == 400
            assert (await c.post("/api/demo", json={"household": "nowhere"}, headers=ME)).status_code == 404
            # the main demo still has its stages
            assert main["stages_available"] == ["capture", "after_handover"]

    run(flow())


def test_steps_can_be_drafted_approved_and_practised():
    async def flow():
        async with await _client() as c:
            h = (await c.post("/api/demo", json={"household": "colombo_care"}, headers=ME)).json()
            hid = h["id"]
            # no approved steps yet for the medicines: practice says so
            r = await c.get(f"/api/households/{hid}/practice/r_meds?person=kasun", headers=ME)
            assert r.status_code == 404
            draft = (await c.get(f"/api/households/{hid}/procedures/r_meds", headers=ME)).json()
            assert not draft["existing"] and draft["steps"][0]["critical"]
            assert any("prescription" in s["text"] for s in draft["steps"])
            # secrets are refused
            bad = {"steps": [{"text": "The PIN is 4821", "critical": True}]}
            assert (await c.put(f"/api/households/{hid}/procedures/r_meds", json=bad, headers=ME)).status_code == 400
            ok = {"steps": draft["steps"], "scenario_prompt": draft["scenario_prompt"]}
            h = (await c.put(f"/api/households/{hid}/procedures/r_meds", json=ok, headers=ME)).json()
            assert any(p["responsibility"] == "r_meds" for p in h["procedures"])
            brief = (await c.get(f"/api/households/{hid}/practice/r_meds?person=kasun", headers=ME)).json()
            assert brief["step_count"] == len(draft["steps"])
            out = (
                await c.post(
                    f"/api/households/{hid}/practice/r_meds/attempts",
                    json={"person": "kasun", "transcript": "No idea.", "hints_given": 0, "mode": "text"},
                    headers=ME,
                )
            ).json()
            assert out["attempt"]["result"] == "not_yet"

    run(flow())


def test_text_is_compressed_for_clients_that_accept_it():
    async def flow():
        async with await _client() as c:
            h = (await c.post("/api/demo", json={}, headers=ME)).json()
            r = await c.get(f"/api/households/{h['id']}", headers={**ME, "Accept-Encoding": "gzip"})
            assert r.status_code == 200 and r.headers.get("content-encoding") == "gzip"
            assert r.json()["id"] == h["id"]  # httpx decodes it as a browser would
            small = await c.get("/api/health", headers={"Accept-Encoding": "gzip"})
            assert "content-encoding" not in small.headers  # tiny answers aren't worth compressing

    run(flow())
