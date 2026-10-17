"""The Perera household end to end: the numbers in the demo come from here."""

import json
from datetime import date

import pytest

from app.domain.household import demo_household, load_gold, load_variants
from app.engine.discover import discover
from app.engine.evaluate import evaluate
from app.engine.repair import plan
from app.engine.serialize import finding_dict, plan_dict, result_dict

GOLD = load_gold("perera")


def run(stage="capture", variant=None):
    h = demo_household("perera", stage, variant)
    c = h.compile()
    assert c.diagnostics == []
    result = evaluate(c.world, c.scenario)
    findings = discover(c.world, c.scenario, result, c.mentions, c.contradictions)
    return h, c, result, findings


@pytest.mark.parametrize("stage", ["capture", "after_handover"])
def test_states_and_summary(stage):
    _, _, result, _ = run(stage)
    gold = GOLD["stages"][stage]
    s = result.summary
    for key, value in gold["summary"].items():
        assert getattr(s, key) == value, key
    assert {rid: r.state.value for rid, r in result.results.items()} == gold["states"]


def test_first_problem_dates_and_occurrences():
    _, _, result, _ = run()
    gold = GOLD["stages"]["capture"]
    for rid, d in gold["first_problem"].items():
        assert result.results[rid].first_problem == d, rid
    for rid, days in gold["occurrences"].items():
        assert [o.date for o in result.results[rid].occurrences] == days, rid


def test_findings_match_gold():
    _, _, _, findings = run()
    by_id = {f.id: f for f in findings}
    for g in GOLD["findings"]:
        f = by_id.get(g["id"])
        assert f is not None, f"missing finding {g['id']}"
        assert f.kind == g["kind"]
        if "responsibilities" in g:
            assert sorted(f.responsibilities) == sorted(g["responsibilities"]), g["id"]
        if "retained" in g:
            got = {c.responsibility: c.code for c in f.considered if c.verdict == "retained"}
            assert got == g["retained"]
            got = {c.responsibility: c.code for c in f.considered if c.verdict == "set_aside"}
            assert got == g["set_aside"]
    flagged = {r for f in findings for r in f.responsibilities}
    for rid in GOLD["must_not_flag"]:
        assert rid not in flagged
    # every finding can be traced to claims
    assert all(f.claim_ids or f.kind == "NOT_ASKED" for f in findings)


def test_plan_matches_gold():
    h, c, result, _ = run()
    p = plan(c.world, c.scenario, result, budget_minutes=GOLD["plan"]["budget_minutes"])
    assert p.exhaustive
    assert p.minutes == GOLD["plan"]["minutes"]
    assert p.after.ready == GOLD["plan"]["after"]["ready"]
    assert p.after.weight_ready == GOLD["plan"]["after"]["weight_ready"]
    assert sorted(b.responsibility for b in p.bundles) == GOLD["plan"]["bundles"]
    clinic = next(b for b in p.bundles if b.responsibility == "r_clinic")
    assert clinic.leaves == GOLD["plan"]["leaves"]["r_clinic"]
    # the honest gap: the booked hire on 24 Dec can't be planned away
    assert all("24 Dec" not in s.title for s in p.steps)


def test_recorded_evidence_reaches_the_planned_result():
    _, c, result, _ = run()
    p = plan(c.world, c.scenario, result, budget_minutes=90)
    _, _, after, _ = run("after_handover")
    assert after.summary.ready == p.after.ready
    assert after.summary.weight_ready == p.after.weight_ready
    blocked = [o.date for o in after.results["r_clinic"].occurrences if not o.prepared]
    assert blocked == GOLD["stages"]["after_handover"]["blocked_dates"]["r_clinic"]


@pytest.mark.parametrize("variant", [v.id for v in load_variants("perera")])
def test_variants_change_the_answer(variant):
    _, _, result, findings = run(variant=variant)
    gold = GOLD["variants"][variant]
    ids = {f.id: f for f in findings}
    for fid in gold.get("no_finding", []):
        assert fid not in ids, fid
    for fid, kind in gold.get("finding_kinds", {}).items():
        assert ids[fid].kind == kind
    for rid, state in gold.get("states", {}).items():
        assert result.results[rid].state.value == state, rid


def test_same_input_same_output():
    def snapshot():
        h, c, result, findings = run()
        p = plan(c.world, c.scenario, result, budget_minutes=90)
        return json.dumps(
            {
                "result": result_dict(c.world, c.scenario, result),
                "findings": [finding_dict(c.world, f) for f in findings],
                "plan": plan_dict(c.world, c.scenario, p),
            },
            sort_keys=True,
            default=str,
        )

    assert snapshot() == snapshot()


def test_headlines_read_like_sentences():
    _, c, result, _ = run()
    d = result_dict(c.world, c.scenario, result)
    heads = {r["id"]: r["headline"] for r in d["responsibilities"]}
    assert heads["r_insurance"] == "Blocked from Fri 20 Nov. Only Nirmala does this, and nobody else has taken it on yet."
    assert heads["r_electricity"] == "Needs confirmation. Sunil hasn't been asked yet."
    assert heads["r_van_fee"].startswith("Blocked on Thu 5 Nov. Sunil is busy on Thu 5 Nov (airport runs")
    assert d["summary"]["sentence"] == "1 of 7 ready for this absence"
    assert d["scenario"]["end_inclusive"] == str(date(2027, 1, 29))
