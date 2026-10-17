"""Compare the engine's conclusions with a household's hand-written gold file.

Each benchmark household has a `gold.yaml` written from its story before the
engine was run on it. This module turns the comparison into a flat list of
checks, used by the test suite (every check must pass) and by the evaluation
harness (which reports precision, recall and accuracy from the same checks).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from ..domain.compile import Compiled
from ..domain.household import Household, available_households, demo_household, load_gold, load_variants
from ..engine.discover import Finding, discover
from ..engine.evaluate import ScenarioResult, evaluate
from ..engine.repair import Plan, plan


@dataclass
class Check:
    household: str
    kind: str  # state | first_problem | summary | blocked_dates | finding | knockout | extra_finding | must_not_flag | plan | variant
    item: str
    expected: Any
    got: Any
    ok: bool
    stage: str = "capture"

    def describe(self) -> str:
        mark = "ok " if self.ok else "FAIL"
        return f"[{mark}] {self.household}/{self.stage} {self.kind} {self.item}: expected {self.expected!r}, got {self.got!r}"


@dataclass
class Run:
    household: Household
    compiled: Compiled
    result: ScenarioResult
    findings: list[Finding]
    plan: Plan | None = None


@dataclass
class GoldReport:
    household: str
    checks: list[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def of(self, kind: str) -> list[Check]:
        return [c for c in self.checks if c.kind == kind]


def run(household_id: str, stage: str = "capture", variant: str | None = None, *, budget: int | None = None) -> Run:
    h = demo_household(household_id, stage, variant)
    c = h.compile()
    result = evaluate(c.world, c.scenario)
    findings = discover(c.world, c.scenario, result, c.mentions, c.contradictions)
    p = plan(c.world, c.scenario, result, budget_minutes=budget) if budget is not None else None
    return Run(h, c, result, findings, p)


def _dates(xs) -> list[str]:
    return [x.isoformat() if isinstance(x, date) else str(x) for x in xs]


def _finding_matches(f: Finding | None, g: dict) -> tuple[bool, dict]:
    if f is None:
        return False, {}
    got: dict[str, Any] = {"kind": f.kind}
    ok = f.kind == g["kind"]
    if "responsibilities" in g:
        got["responsibilities"] = sorted(f.responsibilities)
        ok = ok and got["responsibilities"] == sorted(g["responsibilities"])
    if "retained" in g:
        got["retained"] = {c.responsibility: c.code for c in f.considered if c.verdict == "retained"}
        got["set_aside"] = {c.responsibility: c.code for c in f.considered if c.verdict == "set_aside"}
        ok = ok and got["retained"] == g["retained"] and got["set_aside"] == g.get("set_aside", {})
    return ok, got


def check_household(household_id: str) -> GoldReport:
    gold = load_gold(household_id)
    report = GoldReport(household_id)
    add = report.checks.append

    for stage, g in (gold.get("stages") or {}).items():
        r = run(household_id, stage)
        states = {rid: x.state.value for rid, x in r.result.results.items()}
        for rid, expected in (g.get("states") or {}).items():
            add(Check(household_id, "state", rid, expected, states.get(rid), states.get(rid) == expected, stage))
        for rid, expected in (g.get("first_problem") or {}).items():
            got = r.result.results[rid].first_problem if rid in r.result.results else None
            add(Check(household_id, "first_problem", rid, str(expected), str(got), got == expected, stage))
        for key, expected in (g.get("summary") or {}).items():
            got = getattr(r.result.summary, key)
            add(Check(household_id, "summary", key, expected, got, got == expected, stage))
        for rid, expected in (g.get("blocked_dates") or {}).items():
            got = [o.date for o in r.result.results[rid].occurrences if not o.prepared]
            add(Check(household_id, "blocked_dates", rid, _dates(expected), _dates(got), got == expected, stage))
        for rid, expected in (g.get("occurrences") or {}).items():
            got = [o.date for o in r.result.results[rid].occurrences]
            add(Check(household_id, "occurrences", rid, len(expected), len(got), got == expected, stage))

    base = run(household_id)
    by_id = {f.id: f for f in base.findings}
    gold_ids = set()
    for g in gold.get("findings") or []:
        gold_ids.add(g["id"])
        f = by_id.get(g["id"])
        ok, got = _finding_matches(f, g)
        expected = {k: v for k, v in g.items() if k != "id"}
        add(Check(household_id, "finding", g["id"], expected, got or None, ok))
        if "retained" in g and f is not None:
            # each knockout decision is its own check (used for the ablation numbers)
            decisions = {c.responsibility: (c.verdict, c.code) for c in f.considered}
            for rid, code in g["retained"].items():
                add(
                    Check(
                        household_id,
                        "knockout",
                        f"{g['id']}:{rid}",
                        ("retained", code),
                        decisions.get(rid),
                        decisions.get(rid) == ("retained", code),
                    )
                )
            for rid, code in (g.get("set_aside") or {}).items():
                add(
                    Check(
                        household_id,
                        "knockout",
                        f"{g['id']}:{rid}",
                        ("set_aside", code),
                        decisions.get(rid),
                        decisions.get(rid) == ("set_aside", code),
                    )
                )
    for f in base.findings:
        if f.id not in gold_ids:
            add(Check(household_id, "extra_finding", f.id, None, f.kind, False))
    flagged = {rid for f in base.findings for rid in f.responsibilities}
    for rid in gold.get("must_not_flag") or []:
        add(Check(household_id, "must_not_flag", rid, "not flagged", "flagged" if rid in flagged else "not flagged", rid not in flagged))

    gp = gold.get("plan")
    if gp:
        r = run(household_id, budget=gp["budget_minutes"])
        p = r.plan
        assert p is not None
        add(Check(household_id, "plan", "minutes", gp["minutes"], p.minutes, p.minutes == gp["minutes"]))
        add(Check(household_id, "plan", "after.ready", gp["after"]["ready"], p.after.ready, p.after.ready == gp["after"]["ready"]))
        add(
            Check(
                household_id,
                "plan",
                "after.weight_ready",
                gp["after"]["weight_ready"],
                p.after.weight_ready,
                p.after.weight_ready == gp["after"]["weight_ready"],
            )
        )
        got_bundles = sorted(b.responsibility for b in p.bundles)
        add(Check(household_id, "plan", "bundles", gp["bundles"], got_bundles, got_bundles == sorted(gp["bundles"])))
        for rid, expected in (gp.get("leaves") or {}).items():
            b = next((x for x in p.bundles if x.responsibility == rid), None)
            got = b.leaves if b else None
            add(Check(household_id, "plan", f"leaves:{rid}", _dates(expected), _dates(got or []), got == expected))

    known_variants = {v.id for v in load_variants(household_id)}
    for vid, g in (gold.get("variants") or {}).items():
        if vid not in known_variants:
            add(Check(household_id, "variant", vid, "exists", "missing", False, vid))
            continue
        r = run(household_id, variant=vid)
        ids = {f.id: f for f in r.findings}
        for fid in g.get("no_finding", []):
            add(Check(household_id, "variant", f"no {fid}", "absent", "present" if fid in ids else "absent", fid not in ids, vid))
        for fid, kind in (g.get("finding_kinds") or {}).items():
            got = ids[fid].kind if fid in ids else None
            add(Check(household_id, "variant", f"{fid} kind", kind, got, got == kind, vid))
        for rid, state in (g.get("states") or {}).items():
            got = r.result.results[rid].state.value
            add(Check(household_id, "variant", f"{rid} state", state, got, got == state, vid))
    return report


def benchmark_households() -> list[str]:
    return [h for h in available_households() if load_gold(h)]


__all__ = ["Check", "GoldReport", "Run", "benchmark_households", "check_household", "run"]
