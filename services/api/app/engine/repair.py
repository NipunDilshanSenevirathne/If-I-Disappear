"""Preparation planning: the smallest set of handover steps that does the most.

A repair is a *bundle*: all the steps needed to hand one responsibility over to
one or more willing people (ask, share, register, explain back, show). Single
steps often achieve nothing on their own, which is why we plan whole bundles.

The search is exhaustive over the generated candidate bundles when they fit the
limits (at most one bundle per responsibility, inside the time budget). The
answer is then "the best plan among these options and constraints"; otherwise
it is labelled "best found". It is never claimed to be a global optimum.

Planned effects are hypothetical ("if completed"). The current state changes
only when evidence for a step is recorded and accepted.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta

from .effects import (
    CARD,
    COMMITMENT_OFF,
    DROP_ASSUMPTION,
    FACT_TRUE,
    PRACTICAL,
    SHARE,
    STORE_ON,
    UNDERSTANDING,
    VALID_UNTIL,
    WILLING,
    Effect,
    apply_effects,
)
from .evaluate import Evaluator, ResponsibilityResult, ScenarioResult, Summary, evaluate
from .model import Practical, ResourceKind, Responsibility, Route, Scenario, Understanding, World
from .text import cap, fmt_day, join_and
from .tri import Tri

MAX_BUNDLES_EXHAUSTIVE = 12

UNFIXABLE = {
    "PERFORMER_AWAY",
    "MINOR",
    "NOT_WILLING",
    "WEEKDAY_CLOSED",
    "NO_FREE_DAY",
    "UNAVAILABLE_ON_DATE",
    "EXPIRED",
    "CYCLE",
    "UNKNOWN_RESOURCE",
    "UNKNOWN_PERSON",
    "REQUIREMENTS_UNKNOWN",
    "NO_PERFORMER",
    "NO_ROUTE",
    "VALIDITY_UNKNOWN",
    "ALLOCATION_INCOMPLETE",
    "CAPACITY_CONFLICT",
}
DEPENDENT = {"EXPIRES_NOT_RENEWABLE", "RENEWAL_NOT_READY"}


@dataclass
class Step:
    id: str
    kind: str
    title: str
    owner: str
    collaborators: list[str]
    minutes: int
    minutes_range: tuple[int, int]
    effects: list[Effect]
    evidence: str
    uncertain: bool = False
    responsibility: str | None = None
    note: str = ""
    dates: list[date] = field(default_factory=list)


@dataclass
class Bundle:
    id: str
    responsibility: str
    strategy: str
    label: str
    people: list[str]
    steps: list[Step]
    covers: list[date]
    leaves: list[date]

    @property
    def minutes(self) -> int:
        return sum(s.minutes for s in self.steps)


@dataclass
class Plan:
    budget_minutes: int
    bundles: list[Bundle]
    steps: list[Step]
    minutes: int
    minutes_by_person: dict[str, int]
    before: Summary
    after: Summary
    after_results: dict[str, ResponsibilityResult]
    exhaustive: bool
    evaluated: int
    candidates: list[Bundle] = field(default_factory=list)

    @property
    def label(self) -> str:
        return "Best plan among these options" if self.exhaustive else "Best plan found"


# ---------------------------------------------------------------------- step makers


def _name(world: World, pid: str) -> str:
    return world.people[pid].name if pid in world.people else pid


def _handset_of(world: World, person: str) -> str | None:
    for rid, res in sorted(world.resources.items()):
        if res.kind is ResourceKind.HANDSET and res.holder == person:
            return rid
    return None


def step_ask(world, scenario, resp: Responsibility, person: str) -> Step:
    return Step(
        id=f"ask:{person}:{resp.id}",
        kind="ASK",
        title=f"Ask {_name(world, person)}: can you {resp.label}?",
        owner=scenario.leaver,
        collaborators=[person],
        minutes=2,
        minutes_range=(1, 10),
        effects=[Effect(WILLING, person=person, responsibility=resp.id)],
        evidence="AGREEMENT",
        uncertain=True,
        responsibility=resp.id,
    )


def step_share_contact(world, scenario, contact: str, person: str, handset: str | None) -> Step:
    """Save a contact on the stand-in's own phone. If their phone isn't recorded,
    they simply get their own copy of the number."""
    label = world.resources[contact].label
    effect = Effect(STORE_ON, resource=contact, container=handset) if handset else Effect(SHARE, resource=contact, person=person)
    return Step(
        id=f"share-contact:{contact}:{person}",
        kind="SHARE_CONTACT",
        title=f"Save {label} on {_name(world, person)}'s phone",
        owner=scenario.leaver,
        collaborators=[person],
        minutes=1,
        minutes_range=(1, 3),
        effects=[effect],
        evidence="SELF_REPORT",
    )


def step_send_copy(world, scenario, item: str, account: str, person: str) -> Step:
    """Something that only arrives in the leaver's account (an emailed prescription,
    a statement): have it sent to the stand-in as well."""
    return Step(
        id=f"send-copy:{item}:{person}",
        kind="SEND_COPY",
        title=f"Ask for {world.resources[item].label} to be sent to {_name(world, person)} as well",
        owner=scenario.leaver,
        collaborators=[person],
        minutes=5,
        minutes_range=(2, 20),
        effects=[Effect(SHARE, resource=item, person=person)],
        evidence="SELF_REPORT",
        uncertain=True,
        note=f"Today it only arrives in {world.resources[account].label}.",
    )


def step_share_location(world, scenario, location: str, person: str) -> Step:
    inside = [r.label for r in world.resources.values() if location in r.stored_on]
    items = " and ".join(inside) if inside else world.resources[location].label
    return Step(
        id=f"share-location:{location}:{person}",
        kind="SHARE_LOCATION",
        title=f"Show {_name(world, person)} where {items} {'are' if len(inside) > 1 else 'is'} kept (a photo works)",
        owner=scenario.leaver,
        collaborators=[person],
        minutes=2,
        minutes_range=(1, 5),
        effects=[Effect(SHARE, resource=location, person=person)],
        evidence="PHOTO",
    )


def step_leave_with(world, scenario, rid: str, person: str) -> Step:
    return Step(
        id=f"leave-with:{rid}:{person}",
        kind="LEAVE_WITH",
        title=f"Leave {world.resources[rid].label} with {_name(world, person)}",
        owner=scenario.leaver,
        collaborators=[person],
        minutes=5,
        minutes_range=(2, 15),
        effects=[Effect(SHARE, resource=rid, person=person)],
        evidence="SELF_REPORT",
    )


def step_setup_access(world, scenario, rid: str, person: str) -> Step:
    return Step(
        id=f"setup-access:{rid}:{person}",
        kind="SETUP_ACCESS",
        title=f"Ask the provider how {_name(world, person)} can get their own access to {world.resources[rid].label}",
        owner=scenario.leaver,
        collaborators=[person],
        minutes=60,
        minutes_range=(30, 180),
        effects=[Effect(SHARE, resource=rid, person=person)],
        evidence="PROVIDER_CONFIRMATION",
        uncertain=True,
        note="We only point out the dependency. Check the provider's own rules.",
    )


def step_keep_active(world, scenario, assumption_id: str, rid: str, person: str) -> Step:
    return Step(
        id=f"keep-active:{rid}:{person}",
        kind="KEEP_ACTIVE",
        title=f"Keep {world.resources[rid].label} active and leave it with {_name(world, person)}",
        owner=scenario.leaver,
        collaborators=[person],
        minutes=10,
        minutes_range=(5, 30),
        effects=[Effect(DROP_ASSUMPTION, assumption=assumption_id), Effect(SHARE, resource=rid, person=person)],
        evidence="SELF_REPORT",
        note="This has an ongoing cost.",
    )


def step_enable_fact(world, scenario, fact: str, person: str) -> Step | None:
    enabler = world.fact_enablers.get(fact)
    if enabler is None:
        return None
    owner = scenario.leaver if enabler.owner_role == "leaver" else person
    return Step(
        id=f"enable:{fact}",
        kind="REGISTER",
        title=enabler.label,
        owner=owner,
        collaborators=[person] if owner != person else [],
        minutes=enabler.minutes,
        minutes_range=enabler.minutes_range,
        effects=[Effect(FACT_TRUE, fact=fact)],
        evidence=enabler.evidence,
    )


def step_confirm_fact(world, scenario, fact: str) -> Step:
    label = world.fact_labels.get(fact, fact)
    return Step(
        id=f"confirm:{fact}",
        kind="CONFIRM",
        title=f"Confirm: {label}",
        owner=scenario.leaver,
        collaborators=[],
        minutes=3,
        minutes_range=(1, 15),
        effects=[Effect(FACT_TRUE, fact=fact)],
        evidence="STATEMENT",
        uncertain=True,
    )


def step_swap(world, scenario, person: str, commitment_id: str, day: date) -> Step:
    c = next(c for c in world.commitments if c.id == commitment_id)
    return Step(
        id=f"swap:{commitment_id}:{day.isoformat()}",
        kind="ASK_SWAP",
        title=f"Ask {_name(world, person)}: can you be free on {fmt_day(day)} (instead of {c.label})?",
        owner=scenario.leaver,
        collaborators=[person],
        minutes=15,
        minutes_range=(5, 60),
        effects=[Effect(COMMITMENT_OFF, commitment=commitment_id, day=day)],
        evidence="AGREEMENT",
        uncertain=True,
        note="This may cost them work. Talk it through.",
        dates=[day],
    )


def merge_swaps(world: World, scenario: Scenario, resp: Responsibility, steps: list[Step]) -> list[Step]:
    """One conversation, not one per date: swaps of the same commitment for the same
    responsibility become a single ask that covers all of those dates."""
    groups: dict[str, list[Step]] = {}
    for s in steps:
        if s.kind == "ASK_SWAP":
            commitment = s.effects[0].commitment
            groups.setdefault(commitment, []).append(s)
    out: list[Step] = []
    merged: set[str] = set()
    for s in steps:
        if s.kind != "ASK_SWAP":
            out.append(s)
            continue
        commitment = s.effects[0].commitment
        group = groups[commitment]
        if len(group) == 1:
            out.append(s)
            continue
        if commitment in merged:
            continue
        merged.add(commitment)
        c = next(x for x in world.commitments if x.id == commitment)
        days = sorted(d for g in group for d in g.dates)
        weekdays = sorted({d.weekday() for d in days})
        names = [calendar.day_name[i] + "s" for i in weekdays]
        if len(weekdays) == 1:
            span = f"on {len(days)} {names[0]}"
        elif len(weekdays) <= 3:
            span = f"on {join_and(names)} ({len(days)} dates)"
        else:
            span = f"on {len(days)} dates"
        out.append(
            Step(
                id=f"swap-series:{commitment}:{resp.id}",
                kind="ASK_SWAP",
                title=f"Ask {_name(world, c.person)}: can you be free from {c.label} {span} to {resp.label}?",
                owner=scenario.leaver,
                collaborators=[c.person],
                minutes=15,
                minutes_range=(5, 60),
                effects=[e for g in group for e in g.effects],
                evidence="AGREEMENT",
                uncertain=True,
                responsibility=resp.id,
                note="Dates: " + join_and([fmt_day(d) for d in days]) + ". This may cost them work. Talk it through.",
                dates=days,
            )
        )
    return out


def step_card(world, scenario, resp: Responsibility) -> Step:
    return Step(
        id=f"card:{resp.id}",
        kind="ADD_TO_CARD",
        title=f"Add '{cap(resp.label)}' and its dates to the Continuity Card",
        owner=scenario.leaver,
        collaborators=[],
        minutes=1,
        minutes_range=(1, 3),
        effects=[Effect(CARD, responsibility=resp.id)],
        evidence="APP",
        responsibility=resp.id,
    )


def step_view(world, scenario, resp: Responsibility, person: str) -> Step:
    return Step(
        id=f"view:{person}:{resp.id}",
        kind="VIEW",
        title=f"Send {_name(world, person)} the written steps for '{cap(resp.label)}'",
        owner=scenario.leaver,
        collaborators=[person],
        minutes=2,
        minutes_range=(1, 5),
        effects=[Effect(UNDERSTANDING, person=person, responsibility=resp.id, level=int(Understanding.VIEWED))],
        evidence="APP",
        responsibility=resp.id,
    )


def step_practice(world, scenario, resp: Responsibility, person: str) -> Step:
    return Step(
        id=f"practice:{person}:{resp.id}",
        kind="PRACTICE",
        title=f"{_name(world, person)} explains how to {resp.label}, without help",
        owner=person,
        collaborators=[scenario.leaver],
        minutes=5,
        minutes_range=(3, 15),
        effects=[Effect(UNDERSTANDING, person=person, responsibility=resp.id, level=int(Understanding.UNASSISTED))],
        evidence="PRACTICE",
        responsibility=resp.id,
    )


def step_demo(world, scenario, resp: Responsibility, person: str) -> Step:
    return Step(
        id=f"show:{person}:{resp.id}",
        kind="DEMONSTRATE",
        title=f"{_name(world, person)} shows the key step: {resp.demo_step}",
        owner=person,
        collaborators=[scenario.leaver],
        minutes=3,
        minutes_range=(2, 10),
        effects=[Effect(PRACTICAL, person=person, responsibility=resp.id, level=int(Practical.WITNESSED))],
        evidence="WITNESS",
        responsibility=resp.id,
    )


def step_renew_early(world, scenario, resp: Responsibility, permit: str) -> Step:
    res = world.resources[permit]
    new_date = _add_year(res.valid_until) if res.valid_until else scenario.end
    return Step(
        id=f"renew-early:{permit}",
        kind="RENEW_EARLY",
        title=f"Renew {res.label} before you leave",
        owner=scenario.leaver,
        collaborators=[],
        minutes=45,
        minutes_range=(30, 120),
        effects=[Effect(VALID_UNTIL, resource=permit, new_date=new_date)],
        evidence="DOCUMENT",
        responsibility=resp.id,
        note="Counts when a photo of the renewed document shows the new date.",
    )


def _add_year(d: date) -> date:
    try:
        return d.replace(year=d.year + 1)
    except ValueError:  # 29 Feb
        return d + timedelta(days=365)


# ---------------------------------------------------------------------- fixing one option


def _contact_on_handset(world: World, route: Route, handset: str) -> str | None:
    for req in route.requirements:
        res = world.resources.get(req.target)
        if res and handset in res.stored_on:
            return req.target
    return None


def fix_option(world: World, scenario: Scenario, resp: Responsibility, route: Route, person: str, due: date) -> list[Step] | None:
    """Steps that would make this (route, person) option work AND meet the
    responsibility's evidence policy on `due`. None if it can't be fixed."""
    if person == scenario.leaver or person not in world.people or world.people[person].minor:
        return None
    if route.performers and person not in route.performers:
        return None
    ev = Evaluator(world, scenario)
    option = ev.option(resp, route, person, due)
    steps: list[Step] = []
    for reason in option.reasons:
        code = reason.code
        if reason.kind == "info":
            continue
        if code in UNFIXABLE or code in DEPENDENT:
            return None
        if code == "WILLINGNESS_UNKNOWN":
            steps.append(step_ask(world, scenario, resp, person))
        elif code == "BUSY":
            if reason.refs.get("movable") == "no":
                return None
            steps.append(step_swap(world, scenario, person, reason.refs["commitment"], date.fromisoformat(reason.refs["date"])))
        elif code == "EXPIRES_BEFORE_ABSENCE":
            renewal = world.responsibilities.get(reason.refs.get("responsibility", ""))
            if renewal is None:
                return None
            steps.append(step_renew_early(world, scenario, renewal, reason.refs["resource"]))
        elif code in ("HOLDER_AWAY", "NEEDS_HOLDER"):
            rid = reason.refs["resource"]
            res = world.resources[rid]
            item = reason.refs.get("item")
            if res.kind is ResourceKind.HANDSET:
                contact = item or _contact_on_handset(world, route, rid)
                if not contact:
                    return None
                steps.append(step_share_contact(world, scenario, contact, person, _handset_of(world, person)))
            elif res.kind is ResourceKind.LOCATION:
                steps.append(step_share_location(world, scenario, rid, person))
            elif res.kind in (ResourceKind.DOCUMENT, ResourceKind.ITEM, ResourceKind.NOTE):
                steps.append(step_leave_with(world, scenario, rid, person))
            elif res.kind in (ResourceKind.ACCOUNT, ResourceKind.SERVICE) and item and item != rid:
                # what's needed is something that arrives in the account, not the account itself
                steps.append(step_send_copy(world, scenario, item, rid, person))
            elif res.kind is ResourceKind.ACCOUNT:
                steps.append(step_setup_access(world, scenario, rid, person))
            else:
                return None
        elif code == "SCENARIO_UNAVAILABLE":
            a = next((a for a in scenario.assumptions if a.id == reason.refs.get("assumption")), None)
            if a is None or not a.negotiable:
                return None
            steps.append(step_keep_active(world, scenario, a.id, a.target, person))
        elif code == "FACT_UNKNOWN":
            steps.append(step_confirm_fact(world, scenario, reason.refs["fact"]))
        elif code == "FACT_FALSE":
            s = step_enable_fact(world, scenario, reason.refs["fact"], person)
            if s is None:
                return None
            steps.append(s)
        else:
            return None
    steps = _dedupe(steps)
    applied = apply_effects(world, scenario, [e for s in steps for e in s.effects])
    ev2 = Evaluator(applied.world, applied.scenario)
    option2 = ev2.option(resp, route, person, due)
    if option2.value is not Tri.T:
        return None
    for item in option2.policy_missing:
        if item == "KNOWS_WHEN":
            steps.append(step_card(world, scenario, resp))
        elif item == "VIEW":
            steps.append(step_view(world, scenario, resp, person))
        elif item == "EXPLAIN":
            steps.append(step_practice(world, scenario, resp, person))
        elif item == "SHOW":
            steps.append(step_demo(world, scenario, resp, person))
    return _dedupe(steps)


def _dedupe(steps: list[Step]) -> list[Step]:
    seen: dict[str, Step] = {}
    for s in steps:
        seen.setdefault(s.id, s)
    return list(seen.values())


# ---------------------------------------------------------------------- bundles


def _people_to_consider(world: World, scenario: Scenario, resp: Responsibility) -> list[str]:
    names: list[str] = []
    for route in resp.routes:
        for p in world.candidates(resp, route):
            if p not in names:
                names.append(p)
    for pid, p in sorted(world.people.items()):
        if p.role == "backup" and pid not in names:
            names.append(pid)
    return [p for p in names if p != scenario.leaver and not world.people[p].minor]


def bundles_for(world: World, scenario: Scenario, result: ResponsibilityResult) -> list[Bundle]:
    resp = world.responsibilities[result.id]
    pending = [o for o in result.occurrences if not o.prepared]
    if not pending:
        return []
    people = _people_to_consider(world, scenario, resp)
    # cost table: occurrence date -> person -> (steps)
    table: dict[date, dict[str, list[Step]]] = {}
    for occ in pending:
        row: dict[str, list[Step]] = {}
        for person in people:
            best: list[Step] | None = None
            for route in resp.routes:
                steps = fix_option(world, scenario, resp, route, person, occ.date)
                if steps is None:
                    continue
                if best is None or _cost(steps) < _cost(best):
                    best = steps
            if best is not None:
                row[person] = best
        table[occ.date] = row

    bundles: list[Bundle] = []
    ranked = sorted(
        people,
        key=lambda p: (-sum(1 for d in table if p in table[d]), sum(_cost(table[d][p]) for d in table if p in table[d]), p),
    )
    for primary in ranked[:2]:
        if not any(primary in table[d] for d in table):
            continue
        chosen: dict[str, Step] = {}
        used_people: list[str] = []
        covers: list[date] = []
        leaves: list[date] = []
        for d in sorted(table):
            row = table[d]
            if primary in row:
                pick, steps = primary, row[primary]
            elif row:
                pick = min(row, key=lambda p: (_incremental(row[p], chosen), p))
                steps = row[pick]
            else:
                leaves.append(d)
                continue
            for s in steps:
                chosen.setdefault(s.id, s)
            if pick not in used_people:
                used_people.append(pick)
            covers.append(d)
        names = join_and([_name(world, p) for p in used_people])
        bundles.append(
            Bundle(
                id=f"handover:{resp.id}:{primary}",
                responsibility=resp.id,
                strategy="handover",
                label=f"Hand over to {names}",
                people=used_people,
                steps=merge_swaps(world, scenario, resp, list(chosen.values())),
                covers=covers,
                leaves=leaves,
            )
        )

    # alternative strategy: renew before leaving (permit renewals)
    for rid, res in sorted(world.resources.items()):
        if res.renewed_by == resp.id and res.valid_until and scenario.start <= res.valid_until < scenario.end:
            step = step_renew_early(world, scenario, resp, rid)
            bundles.append(
                Bundle(
                    id=f"renew-early:{resp.id}",
                    responsibility=resp.id,
                    strategy="renew_early",
                    label="Renew it before you leave",
                    people=[scenario.leaver],
                    steps=[step],
                    covers=[o.date for o in pending],
                    leaves=[],
                )
            )
    # identical step sets are the same bundle
    unique: dict[frozenset, Bundle] = {}
    for b in bundles:
        unique.setdefault(frozenset(s.id for s in b.steps), b)
    return list(unique.values())


def _cost(steps: list[Step]) -> int:
    return sum(s.minutes for s in steps)


def _incremental(steps: list[Step], chosen: dict[str, Step]) -> int:
    return sum(s.minutes for s in steps if s.id not in chosen)


# ---------------------------------------------------------------------- optimiser


def plan(world: World, scenario: Scenario, base: ScenarioResult | None = None, budget_minutes: int = 60) -> Plan:
    base = base or evaluate(world, scenario)
    candidates: list[Bundle] = []
    for _rid, r in sorted(base.results.items()):
        if not r.state.ready:
            candidates.extend(bundles_for(world, scenario, r))

    groups: dict[str, list[Bundle]] = {}
    for b in candidates:
        groups.setdefault(b.responsibility, []).append(b)
    exhaustive = len(candidates) <= MAX_BUNDLES_EXHAUSTIVE
    if not exhaustive:
        # keep the two most promising bundles per responsibility
        for k in list(groups):
            groups[k] = sorted(groups[k], key=lambda b: (-len(b.covers), b.minutes, b.id))[:2]
    group_items = sorted(groups.items())

    memo: dict[frozenset, tuple] = {}
    evaluated = 0
    best: dict = {"key": None, "selection": None, "result": None}

    def score(selection: list[Bundle]):
        nonlocal evaluated
        steps = _union_steps(selection)
        key = frozenset(steps)
        if key in memo:
            return memo[key]
        evaluated += 1
        applied = apply_effects(world, scenario, [e for s in steps.values() for e in s.effects])
        result = evaluate(applied.world, applied.scenario)
        minutes = sum(s.minutes for s in steps.values())
        load: dict[str, int] = {}
        for s in steps.values():
            load[s.owner] = load.get(s.owner, 0) + s.minutes
        objective = (
            round(result.summary.occurrence_coverage, 6),
            result.summary.weight_ready,
            -max(load.values(), default=0),
            -minutes,
            -len(steps),
        )
        memo[key] = (objective, result)
        return memo[key]

    def dfs(i: int, selection: list[Bundle]):
        if i == len(group_items):
            objective, result = score(selection)
            # strict ">" keeps the first selection found on exact ties; DFS order is
            # deterministic, so the plan is stable for the same inputs
            if best["key"] is None or objective > best["key"]:
                best.update(key=objective, selection=list(selection), result=result)
            return
        _, options = group_items[i]
        dfs(i + 1, selection)
        for b in options:
            trial = selection + [b]
            if _minutes(trial) <= budget_minutes:
                dfs(i + 1, trial)

    dfs(0, [])
    selection: list[Bundle] = best["selection"] or []
    result = best["result"] or base
    steps = _union_steps(selection)
    by_person: dict[str, int] = {}
    for s in steps.values():
        by_person[s.owner] = by_person.get(s.owner, 0) + s.minutes
    return Plan(
        budget_minutes=budget_minutes,
        bundles=sorted(selection, key=lambda b: b.responsibility),
        steps=list(steps.values()),
        minutes=sum(s.minutes for s in steps.values()),
        minutes_by_person=by_person,
        before=base.summary,
        after=result.summary,
        after_results=result.results,
        exhaustive=exhaustive,
        evaluated=evaluated,
        candidates=candidates,
    )


def _union_steps(selection: list[Bundle]) -> dict[str, Step]:
    steps: dict[str, Step] = {}
    for b in selection:
        for s in b.steps:
            steps.setdefault(s.id, s)
    return steps


def _minutes(selection: list[Bundle]) -> int:
    return sum(s.minutes for s in _union_steps(selection).values())
