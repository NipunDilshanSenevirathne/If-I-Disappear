"""Turn engine results into plain-language, JSON-ready structures for the API/UI.

Wording rules: plain verbs, sentence case, say what happened and what to do.
Numbers shown to people always come from these structures, never from a model.
"""

from __future__ import annotations

from datetime import date, timedelta

from .discover import Finding
from .evaluate import OccurrenceResult, Reason, ResponsibilityResult, ScenarioResult, State, Summary
from .model import Scenario, World
from .repair import Bundle, Plan, Step
from .text import join_and
from .tri import Tri

STATE_TEXT = {
    State.PREPARED: "Ready",
    State.NEEDS_HANDOVER: "Handover not finished",
    State.NEEDS_CONFIRMATION: "Needs confirmation",
    State.BLOCKED: "Blocked",
    State.NOT_DUE: "Nothing due while away",
}

MISSING_TEXT = {
    "KNOWS_WHEN": "doesn't have the dates yet",
    "VIEW": "hasn't seen the steps",
    "EXPLAIN": "hasn't explained it back without help",
    "SHOW": "hasn't shown the key step",
}


def d(x: date | None) -> str | None:
    return x.isoformat() if x else None


def nice(x: date) -> str:
    return x.strftime("%a %d %b").replace(" 0", " ")


def name(world: World, pid: str | None) -> str:
    if pid and pid in world.people:
        return world.people[pid].name
    return pid or ""


def reason_dict(r: Reason) -> dict:
    return {"code": r.code, "message": r.message, "kind": r.kind, "refs": r.refs, "claim_ids": list(r.claim_ids)}


def occurrence_dict(world: World, resp_id: str, o: OccurrenceResult) -> dict:
    resp = world.responsibilities[resp_id]
    routes = {r.id: r for r in resp.routes}
    chosen = None
    if o.chosen is not None:
        route = routes.get(o.chosen.route_id)
        chosen = {
            "route_id": o.chosen.route_id,
            "route_label": route.label if route else o.chosen.route_id,
            "person": o.chosen.person,
            "person_name": name(world, o.chosen.person),
            "day": d(o.chosen.day),
            "window": o.chosen.window_label,
            "missing": [{"code": m, "text": MISSING_TEXT.get(m, m)} for m in o.chosen.policy_missing],
        }
    options = []
    for opt in o.options:
        route = routes.get(opt.route_id)
        options.append(
            {
                "route_id": opt.route_id,
                "route_label": route.label if route else opt.route_id,
                "person": opt.person,
                "person_name": name(world, opt.person),
                "value": opt.value.value,
                "reasons": [reason_dict(r) for r in opt.reasons],
            }
        )
    return {
        "date": d(o.date),
        "label": nice(o.date),
        "act_by": d(o.act_by),
        "value": o.value.value,
        "prepared": o.prepared,
        "chosen": chosen,
        "reasons": [reason_dict(r) for r in o.reasons],
        "options": options,
    }


def problem_occurrence(r: ResponsibilityResult) -> OccurrenceResult | None:
    """The date that explains the state: for a block, the first date nothing works
    (which can come after dates that only need a handover); for a question, the
    first unknown date; otherwise the first date that isn't ready."""
    pending = [o for o in r.occurrences if not o.prepared]
    if r.state is State.BLOCKED:
        hit = next((o for o in pending if o.value is Tri.F), None)
        if hit:
            return hit
    if r.state in (State.BLOCKED, State.NEEDS_CONFIRMATION):
        hit = next((o for o in pending if o.value is Tri.U), None)
        if hit:
            return hit
    return pending[0] if pending else None


def headline(world: World, r: ResponsibilityResult, leaver: str | None = None) -> str:
    """One sentence a person can act on: the state, the first date it bites, and why."""
    if r.state is State.NOT_DUE:
        return "Nothing is due during this absence."
    if r.state is State.PREPARED:
        people = join_and([name(world, p) for p in r.performers])
        return f"{people} will take care of it."
    problem = problem_occurrence(r)
    if r.state is State.NEEDS_HANDOVER:
        bits = []
        for person, items in r.missing.items():
            bits.append(f"{name(world, person)} " + join_and([MISSING_TEXT.get(i, i) for i in items]))
        return "It works, but " + "; ".join(bits) + "."
    if problem is None:
        return STATE_TEXT[r.state]
    top = _top_reason(problem)
    when = nice(problem.date)
    stand_in = any(o.person and o.person != leaver for o in problem.options)
    message = top.message if top else ""
    if not stand_in and leaver is not None:
        resp = world.responsibilities[r.id]
        owners = [p for p in resp.owners if p != leaver] or resp.owners
        who = join_and([name(world, p) for p in owners]) or name(world, leaver)
        message = (message + " " if message else "") + (
            "Nobody else has taken this on yet." if top else f"Only {who} does this, and nobody else has taken it on yet."
        )
    if r.state is State.BLOCKED:
        # "from" when it stays blocked after that date, "on" when later dates still work
        stays = all(o.value is Tri.F for o in r.occurrences if o.date > problem.date)
        prefix = f"Blocked from {when}" if stays else f"Blocked on {when}"
        return f"{prefix}. {message}".strip() if message else prefix + "."
    return f"Needs confirmation. {message}".strip() if message else "Needs confirmation."


_ORDER = [
    "CAPACITY_CONFLICT",
    "BUSY",
    "UNAVAILABLE_ON_DATE",
    "HOLDER_AWAY",
    "SCENARIO_UNAVAILABLE",
    "EXPIRES_BEFORE_ABSENCE",
    "EXPIRES_NOT_RENEWABLE",
    "EXPIRED",
    "FACT_FALSE",
    "WILLINGNESS_UNKNOWN",
    "FACT_UNKNOWN",
    "RENEWAL_NOT_READY",
    "NEEDS_HOLDER",
]


def _top_reason(o: OccurrenceResult) -> Reason | None:
    """The reason to show first. For an unknown, the open question; for a block,
    the hardest constraint (a booked commitment before a movable one)."""
    reasons = [r for r in o.reasons if r.code != "PERFORMER_AWAY"]

    def key(r: Reason):
        idx = _ORDER.index(r.code) if r.code in _ORDER else 99
        fixed = 0 if r.refs.get("movable") == "no" else 1
        unknown_first = 0 if (o.value is Tri.U and r.kind == "unknown") else 1
        return (unknown_first, idx, fixed)

    reasons.sort(key=key)
    return reasons[0] if reasons else None


def explanation_path(world: World, scenario: Scenario, r: ResponsibilityResult) -> list[dict]:
    """A short chain from cause to consequence for the date that explains the state."""
    problem = problem_occurrence(r)
    nodes: list[dict] = []
    resp = world.responsibilities[r.id]
    if problem is None:
        return [{"kind": "responsibility", "id": r.id, "label": r.label, "status": r.state.value}]
    if scenario.leaver in resp.owners:
        nodes.append(
            {"kind": "person", "id": scenario.leaver, "label": f"{name(world, scenario.leaver)} is away from {nice(scenario.start)}"}
        )
    seen = set()
    for reason in problem.reasons:
        if reason.code == "PERFORMER_AWAY":
            continue
        key = reason.key()
        if key in seen:
            continue
        seen.add(key)
        kind = {
            "HOLDER_AWAY": "resource",
            "NEEDS_HOLDER": "resource",
            "SCENARIO_UNAVAILABLE": "assumption",
            "BUSY": "commitment",
            "UNAVAILABLE_ON_DATE": "person",
            "FACT_FALSE": "fact",
            "FACT_UNKNOWN": "fact",
            "WILLINGNESS_UNKNOWN": "person",
            "EXPIRES_NOT_RENEWABLE": "resource",
            "RENEWAL_NOT_READY": "resource",
            "CAPACITY_CONFLICT": "date",
        }.get(reason.code, "reason")
        nodes.append(
            {
                "kind": kind,
                "id": reason.refs.get("resource") or reason.refs.get("person") or reason.refs.get("fact") or reason.code,
                "label": reason.message,
                "claim_ids": list(reason.claim_ids),
            }
        )
    nodes.append({"kind": "date", "id": problem.date.isoformat(), "label": nice(problem.date)})
    nodes.append({"kind": "responsibility", "id": r.id, "label": r.label, "status": r.state.value})
    return nodes


def responsibility_dict(world: World, scenario: Scenario, r: ResponsibilityResult) -> dict:
    resp = world.responsibilities[r.id]
    covered = sum(1 for o in r.occurrences if o.prepared)
    return {
        "id": r.id,
        "label": r.label,
        "category": resp.category,
        "weight": r.weight,
        "state": r.state.value,
        "state_text": STATE_TEXT[r.state],
        "feasibility": r.feasibility.value,
        "headline": headline(world, r, scenario.leaver),
        "first_problem": d(r.first_problem),
        "problem_date": d(p.date) if (p := problem_occurrence(r)) else None,
        "performers": [{"id": p, "name": name(world, p)} for p in r.performers],
        "missing": {p: [{"code": m, "text": MISSING_TEXT.get(m, m)} for m in items] for p, items in r.missing.items()},
        "occurrences_total": len(r.occurrences),
        "occurrences_ready": covered,
        "recurrence": resp.recurrence.label(),
        "owners": [{"id": p, "name": name(world, p)} for p in resp.owners],
        "policy": resp.policy.value,
        "occurrences": [occurrence_dict(world, r.id, o) for o in r.occurrences],
        "path": explanation_path(world, scenario, r),
        "claim_ids": list(resp.claim_ids),
    }


def summary_dict(s: Summary) -> dict:
    return {
        "total": s.total,
        "ready": s.ready,
        "prepared": s.prepared,
        "not_due": s.not_due,
        "needs_handover": s.needs_handover,
        "needs_confirmation": s.needs_confirmation,
        "blocked": s.blocked,
        "weight_total": s.weight_total,
        "weight_ready": s.weight_ready,
        "ready_pct": s.ready_pct,
        "occurrence_coverage": round(s.occurrence_coverage, 4),
        "sentence": f"{s.ready} of {s.total} ready for this absence" if s.total else "No responsibilities selected",
    }


def scenario_dict(world: World, scenario: Scenario) -> dict:
    return {
        "id": scenario.id,
        "label": scenario.label,
        "leaver": scenario.leaver,
        "leaver_name": name(world, scenario.leaver),
        "start": d(scenario.start),
        "end_exclusive": d(scenario.end),
        "end_inclusive": d(scenario.end - timedelta(days=1)),
        "days": (scenario.end - scenario.start).days,
        "assumptions": [
            {"id": a.id, "kind": a.kind, "target": a.target, "label": a.label, "negotiable": a.negotiable, "claim_ids": list(a.claim_ids)}
            for a in scenario.assumptions
        ],
    }


def result_dict(world: World, scenario: Scenario, result: ScenarioResult) -> dict:
    return {
        "scenario": scenario_dict(world, scenario),
        "world_version": result.world_version,
        "engine_version": result.engine_version,
        "policy_version": result.policy_version,
        "summary": summary_dict(result.summary),
        "responsibilities": [responsibility_dict(world, scenario, r) for r in _ordered(result)],
        "timeline": timeline(world, result),
        "diagnostics": result.diagnostics,
    }


def _ordered(result: ScenarioResult) -> list[ResponsibilityResult]:
    from .evaluate import SEVERITY

    return sorted(result.results.values(), key=lambda r: (-SEVERITY[r.state], -r.weight, r.first_problem or date.max, r.id))


def timeline(world: World, result: ScenarioResult) -> list[dict]:
    """Dated events across the absence: every occurrence with its status."""
    events = []
    for r in result.results.values():
        for o in r.occurrences:
            status = "ready" if o.prepared else ("blocked" if o.value is Tri.F else "unknown" if o.value is Tri.U else "handover")
            events.append(
                {
                    "date": d(o.date),
                    "label": nice(o.date),
                    "responsibility": r.id,
                    "responsibility_label": r.label,
                    "status": status,
                    "message": (_top_reason(o).message if (_top_reason(o) and not o.prepared and o.value is not Tri.T) else None),
                    "person": name(world, o.chosen.person) if o.chosen else None,
                }
            )
    events.sort(key=lambda e: (e["date"], e["responsibility"]))
    return events


def finding_dict(world: World, f: Finding) -> dict:
    return {
        "id": f.id,
        "kind": f.kind,
        "title": f.title,
        "summary": f.summary,
        "severity": f.severity,
        "responsibilities": [
            {"id": r, "label": world.responsibilities[r].label} for r in f.responsibilities if r in world.responsibilities
        ],
        "dates": [d(x) for x in f.dates],
        "path": [{"kind": n.kind, "id": n.id, "label": n.label, "status": n.status, "claim_ids": list(n.claim_ids)} for n in f.path],
        "claim_ids": list(f.claim_ids),
        "considered": [
            {
                "responsibility": c.responsibility,
                "label": world.responsibilities[c.responsibility].label,
                "verdict": c.verdict,
                "code": c.code,
                "message": c.message,
                "claim_ids": list(c.claim_ids),
            }
            for c in f.considered
        ],
        "assumptions": f.assumptions,
        "questions": f.questions,
        "status": f.status,
        "challenge": f.challenge,
        "asks": f.asks,
        "rank": round(f.rank, 2),
    }


def step_dict(world: World, s: Step) -> dict:
    return {
        "id": s.id,
        "kind": s.kind,
        "title": s.title,
        "owner": s.owner,
        "owner_name": name(world, s.owner),
        "collaborators": [{"id": p, "name": name(world, p)} for p in s.collaborators],
        "minutes": s.minutes,
        "minutes_range": list(s.minutes_range),
        "evidence": s.evidence,
        "uncertain": s.uncertain,
        "responsibility": s.responsibility,
        "note": s.note,
    }


def bundle_dict(world: World, b: Bundle) -> dict:
    return {
        "id": b.id,
        "responsibility": b.responsibility,
        "responsibility_label": world.responsibilities[b.responsibility].label,
        "strategy": b.strategy,
        "label": b.label,
        "people": [{"id": p, "name": name(world, p)} for p in b.people],
        "minutes": b.minutes,
        "covers": [d(x) for x in b.covers],
        "leaves": [d(x) for x in b.leaves],
        "steps": [step_dict(world, s) for s in b.steps],
    }


def plan_dict(world: World, scenario: Scenario, p: Plan) -> dict:
    return {
        "budget_minutes": p.budget_minutes,
        "label": p.label,
        "exhaustive": p.exhaustive,
        "evaluated": p.evaluated,
        "minutes": p.minutes,
        "minutes_by_person": [{"id": k, "name": name(world, k), "minutes": v} for k, v in sorted(p.minutes_by_person.items())],
        "before": summary_dict(p.before),
        "after": summary_dict(p.after),
        "after_states": {
            rid: {
                "state": r.state.value,
                "state_text": STATE_TEXT[r.state],
                "occurrences_ready": sum(1 for o in r.occurrences if o.prepared),
                "occurrences_total": len(r.occurrences),
            }
            for rid, r in p.after_results.items()
        },
        "bundles": [bundle_dict(world, b) for b in p.bundles],
        "steps": [step_dict(world, s) for s in p.steps],
        "alternatives": [bundle_dict(world, b) for b in p.candidates if b.id not in {x.id for x in p.bundles}],
        "note": "Planned effects are hypothetical. Your current result changes only when the evidence for a step is recorded.",
    }
