"""The Continuity Card: one printable page that tells the family who does what, when,
how, and where things are. Built from the engine's results, never from a model.

It carries no secrets: no passwords, PINs, account numbers or full phone numbers.
Contacts are named with where they're saved, not their numbers.
"""

from __future__ import annotations

from datetime import date, timedelta

from ..domain.household import Household
from ..engine.evaluate import State, evaluate
from ..engine.model import ResourceKind, World
from ..engine.serialize import headline, nice
from ..engine.text import join_and


def _where(world: World, rid: str, seen: set[str]) -> list[dict]:
    """Where a needed thing is: the place it's kept or the phone it's saved on."""
    out: list[dict] = []
    res = world.resources.get(rid)
    if res is None or rid in seen:
        return out
    seen.add(rid)
    for container in res.stored_on:
        c = world.resources.get(container)
        if c is None:
            continue
        if c.kind is ResourceKind.LOCATION:
            out.append({"kind": "place", "item": res.label, "where": c.label})
        elif c.kind is ResourceKind.HANDSET:
            out.append({"kind": "contact", "item": res.label, "where": c.label})
    for req in res.requires:
        out += _where(world, req, seen)
    return out


async def build_card(h: Household, only: set[str] | None = None) -> dict:
    """The card for every responsibility, or only the ones in `only` (a shared handover)."""
    c = h.compile()
    world, scenario = c.world, c.scenario
    result = evaluate(world, scenario)
    procedures = {p.responsibility: p for p in h.procedures}
    items = []
    gaps = []
    for rid, r in sorted(result.results.items(), key=lambda kv: (-kv[1].weight, kv[0])):
        if only is not None and rid not in only:
            continue
        resp = world.responsibilities[rid]
        dates = [o.date for o in r.occurrences]
        chosen = next((o.chosen for o in r.occurrences if o.chosen is not None), None)
        route = next((rt for rt in resp.routes if chosen and rt.id == chosen.route_id), resp.routes[0] if resp.routes else None)
        who = join_and([world.people[p].name for p in r.performers if p in world.people]) or None
        where: list[dict] = []
        if route:
            seen: set[str] = set()
            for req in route.requirements:
                where += _where(world, req.target, seen)
        proc = procedures.get(rid)
        steps = []
        if proc:
            for s in proc.steps:
                steps.append({"id": s.id, "text": s.text, "critical": s.critical})
        for o in r.occurrences:
            if not o.prepared and r.state is not State.NOT_DUE:
                msg = headline(world, r, scenario.leaver) if o is next((x for x in r.occurrences if not x.prepared), None) else None
                gaps.append(
                    {"responsibility": rid, "label": resp.label, "date": o.date.isoformat(), "date_label": nice(o.date), "message": msg}
                )
        items.append(
            {
                "responsibility": rid,
                "label": resp.label,
                "category": resp.category,
                "weight": resp.weight,
                "state": r.state.value,
                "who": who,
                "when": resp.recurrence.label(),
                "dates": [d.isoformat() for d in dates],
                "next": nice(dates[0]) if dates else None,
                "act_by": (dates[0] - timedelta(days=resp.lead_days)).isoformat() if dates and resp.lead_days else None,
                "route": route.label if route else None,
                "key_step": resp.demo_step,
                "steps": steps,
                "where": where,
                "on_card": rid in world.card_entries,
            }
        )

    leaver = world.people.get(scenario.leaver)
    ready = sum(1 for i in items if i["state"] in (State.PREPARED.value, State.NOT_DUE.value))
    return {
        "household": h.settings.name,
        "leaver": leaver.name if leaver else scenario.leaver,
        "from": scenario.start.isoformat(),
        "to": (scenario.end - timedelta(days=1)).isoformat(),
        "generated": date.today().isoformat(),
        "synthetic": h.settings.synthetic,
        "summary": {"ready": result.summary.ready, "total": result.summary.total}
        if only is None
        else {"ready": ready, "total": len(items)},
        "items": items,
        "gaps": gaps,
        "no_secrets": True,
    }
