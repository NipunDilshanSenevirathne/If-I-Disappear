"""Explore: "what if someone else is away too, or the car isn't there?"

The household changes nothing. The engine evaluates a *copy* of the absence with
the extra assumptions the person picked, and returns what would change, next to
the result as recorded. Same engine, same rules, no model involved, so the
answer is instant and repeatable.
"""

from __future__ import annotations

from datetime import date, timedelta

from ..domain.household import Household
from ..engine.evaluate import SEVERITY, evaluate
from ..engine.model import Assumption, ResourceKind
from ..engine.serialize import headline, nice, scenario_dict, summary_dict

TOGGLE_KINDS = {
    ResourceKind.PHONE_NUMBER,
    ResourceKind.HANDSET,
    ResourceKind.ACCOUNT,
    ResourceKind.VEHICLE,
    ResourceKind.SERVICE,
    ResourceKind.CONTACT,
    ResourceKind.DOCUMENT,
}


class ExploreError(ValueError):
    pass


def options(h: Household) -> dict:
    """What can be switched in Explore: other adults, things the household uses, and
    the assumptions already recorded (which the household can lift)."""
    c = h.compile()
    world, scenario = c.world, c.scenario
    people = [
        {"id": p.id, "name": p.name} for p in sorted(world.people.values(), key=lambda p: p.name) if p.id != scenario.leaver and not p.minor
    ]
    things = [
        {"id": r.id, "name": r.label, "kind": r.kind.value}
        for r in sorted(world.resources.values(), key=lambda r: (r.kind.value, r.label))
        if r.kind in TOGGLE_KINDS
    ]
    assumptions = [{"id": a.id, "label": a.label, "negotiable": a.negotiable} for a in scenario.assumptions]
    return {
        "people": people,
        "things": things,
        "assumptions": assumptions,
        "departure": scenario.start.isoformat(),
        "days": (scenario.end - scenario.start).days,
    }


def explore(
    h: Household,
    *,
    also_away: list[str] | None = None,
    unavailable: list[str] | None = None,
    keep_using: list[str] | None = None,
    departure: date | None = None,
    days: int | None = None,
) -> dict:
    c = h.compile()
    world, base_scenario = c.world, c.scenario
    base = evaluate(world, base_scenario)

    s = base_scenario.copy()
    changes: list[str] = []
    if departure is not None or days is not None:
        start = departure or s.start
        length = days or (s.end - s.start).days
        if not 1 <= length <= 365:
            raise ExploreError("Choose between 1 and 365 days.")
        s.start, s.end = start, start + timedelta(days=length)
        changes.append(f"Away from {nice(s.start)} for {length} days")
    lifted = set(keep_using or [])
    for a in list(s.assumptions):
        if a.id in lifted:
            s.assumptions.remove(a)
            thing = world.resources[a.target].label if a.target in world.resources else a.label
            changes.append(f"Keep using {thing}")
    for pid in sorted(set(also_away or [])):
        if pid not in world.people or pid == s.leaver:
            raise ExploreError("Choose someone from the household.")
        s.assumptions.append(
            Assumption(id=f"explore:away:{pid}", kind="person_absent", target=pid, label=f"{world.people[pid].name} is away too")
        )
        changes.append(f"{world.people[pid].name} is away too")
    for rid in sorted(set(unavailable or [])):
        if rid not in world.resources:
            raise ExploreError("Choose something the household uses.")
        s.assumptions.append(
            Assumption(
                id=f"explore:off:{rid}", kind="resource_unavailable", target=rid, label=f"{world.resources[rid].label} isn't available"
            )
        )
        changes.append(f"{world.resources[rid].label} isn't available")

    after = evaluate(world, s)
    rows = []
    for rid in sorted(after.results, key=lambda r: (-SEVERITY[after.results[r].state], r)):
        a = after.results[rid]
        b = base.results.get(rid)
        rows.append(
            {
                "id": rid,
                "label": world.responsibilities[rid].label,
                "before": b.state.value if b else None,
                "after": a.state.value,
                "changed": b is None or b.state is not a.state,
                "worse": b is not None and SEVERITY[a.state] > SEVERITY[b.state],
                "better": b is not None and SEVERITY[a.state] < SEVERITY[b.state],
                "headline": headline(world, a, s.leaver),
                "occurrences_ready": sum(1 for o in a.occurrences if o.prepared),
                "occurrences_total": len(a.occurrences),
            }
        )
    return {
        "changes": changes,
        "scenario": scenario_dict(world, s),
        "before": summary_dict(base.summary),
        "after": summary_dict(after.summary),
        "responsibilities": rows,
        "worse": sum(1 for r in rows if r["worse"]),
        "better": sum(1 for r in rows if r["better"]),
    }
