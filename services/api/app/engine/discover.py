"""Discovery: find what nobody said, and set aside what isn't true.

Each finding is produced by code from the compiled model and a scenario result,
and carries its explanation path, supporting claims and the items that were
considered and set aside (counterevidence). The AI challenger reviews findings
afterwards; it can narrow or question them but never invent new ones.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .evaluate import SEVERITY, Evaluator, Reason, ResponsibilityResult, ScenarioResult, evaluate
from .model import ReqKind, Responsibility, Route, Scenario, World
from .text import cap, fmt_day, join_and
from .tri import Tri


@dataclass
class Mention:
    """A source mentioning a resource, and what (if anything) it links it to."""

    source_id: str
    claim_id: str
    responsibility: str | None
    role: str  # requires | notifies | contact | mentioned


@dataclass
class PathNode:
    kind: str  # person | assumption | resource | commitment | fact | date | responsibility | route
    id: str
    label: str
    status: str | None = None
    claim_ids: tuple[str, ...] = ()


@dataclass
class Considered:
    responsibility: str
    verdict: str  # retained | set_aside
    code: str
    message: str
    claim_ids: tuple[str, ...] = ()


@dataclass
class Contradiction:
    id: str
    subject: str
    field: str
    values: list[tuple[str, str]]  # (value, claim id)
    responsibility: str | None
    label: str


@dataclass
class Finding:
    id: str
    kind: str
    title: str
    summary: str
    severity: int
    responsibilities: list[str]
    dates: list[date]
    path: list[PathNode]
    claim_ids: list[str]
    considered: list[Considered] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    status: str = "candidate"  # candidate | retained | narrowed | rejected | ask
    rank: float = 0.0
    challenge: dict | None = None
    asks: list[dict] = field(default_factory=list)  # NOT_ASKED: [{person, responsibility, question}]


# ---------------------------------------------------------------------- graph helpers


def route_depends_on(world: World, route: Route, rid: str) -> bool:
    return any(req.kind is ReqKind.ACCESS and _reaches(world, req.target, rid, set()) for req in route.requirements)


def _reaches(world: World, start: str, target: str, seen: set[str]) -> bool:
    if start == target:
        return True
    if start in seen:
        return False
    seen.add(start)
    res = world.resources.get(start)
    if res is None:
        return False
    for nxt in list(res.requires) + list(res.stored_on):
        if _reaches(world, nxt, target, seen):
            return True
    return False


def responsibilities_using(world: World, rid: str) -> set[str]:
    used: set[str] = set()
    for resp in world.responsibilities.values():
        if not resp.in_scope:
            continue
        if any(route_depends_on(world, r, rid) for r in resp.routes):
            used.add(resp.id)
        if any(_reaches(world, s, rid, set()) for s in resp.awareness_sources):
            used.add(resp.id)
    return used


def _reasons_mention(reasons: list[Reason], rid: str) -> bool:
    return any(r.refs.get("resource") == rid for r in reasons)


def _best_route_value(world: World, result: ResponsibilityResult, route: Route) -> Tri:
    values = [o.value for occ in result.occurrences[:1] for o in occ.options if o.route_id == route.id]
    if Tri.T in values:
        return Tri.T
    if Tri.U in values:
        return Tri.U
    return Tri.F


def _name(world: World, person: str | None) -> str:
    if person and person in world.people:
        return world.people[person].name
    return person or "someone"


def _fmt(d: date) -> str:
    return fmt_day(d)


# ---------------------------------------------------------------------- discovery


def discover(
    world: World,
    scenario: Scenario,
    base: ScenarioResult,
    mentions: dict[str, list[Mention]] | None = None,
    contradictions: list[Contradiction] | None = None,
) -> list[Finding]:
    mentions = mentions or {}
    findings: list[Finding] = []
    findings += shared_dependency_findings(world, scenario, base, mentions)
    findings += held_by_leaver_findings(world, scenario, base)
    findings += schedule_clash_findings(world, scenario, base)
    findings += deadline_findings(world, scenario, base)
    findings += not_asked_findings(world, scenario, base)
    findings += contradiction_findings(world, contradictions or [])
    for f in findings:
        f.rank = _rank(world, base, f, scenario)
    findings.sort(key=lambda f: (-f.rank, f.id))
    return findings


def shared_dependency_findings(world, scenario, base, mentions) -> list[Finding]:
    """Association + knockout: a resource that shows up across several sources is a
    *candidate* shared dependency. We then test each linked responsibility and keep
    only those where the resource really matters."""
    out: list[Finding] = []
    for rid in sorted(world.resources):
        res = world.resources[rid]
        if res.generic or res.kind.value in ("handset", "location"):
            continue  # containers are covered by held-by-leaver findings
        ms = mentions.get(rid, [])
        sources = sorted({m.source_id for m in ms})
        linked = {m.responsibility for m in ms if m.responsibility in world.responsibilities}
        linked |= responsibilities_using(world, rid)
        linked = {r for r in linked if world.responsibilities[r].in_scope and r in base.results}
        if len(linked) < 2 or len(sources) < 2:
            continue

        # Counterfactual: the resource stays in use and is shared with every adult at home.
        w2 = world.copy()
        s2 = scenario.copy()
        s2.assumptions = [a for a in s2.assumptions if not (a.kind == "resource_unavailable" and a.target == rid)]
        for pid, person in world.people.items():
            if pid != scenario.leaver and not person.minor:
                w2.resources[rid].shared_with.add(pid)
        cf = evaluate(w2, s2)

        considered: list[Considered] = []
        ev = Evaluator(world, scenario)
        for resp_id in sorted(linked):
            resp = world.responsibilities[resp_id]
            b = base.results[resp_id]
            c = cf.results[resp_id]
            considered.append(_classify(world, scenario, ev, resp, b, c, rid))
        considered.sort(key=lambda c: (c.verdict != "retained", c.responsibility))
        retained = [c for c in considered if c.verdict == "retained"]
        if not retained:
            continue
        claim_ids = sorted({m.claim_id for m in ms} | set(res.claim_ids))
        assumption_ids = [a.id for a in scenario.assumptions if a.target == rid]
        only_route = [world.responsibilities[c.responsibility].label for c in retained if c.code == "ONLY_ROUTE"]
        only_reminder = [world.responsibilities[c.responsibility].label for c in retained if c.code == "ONLY_REMINDER"]
        set_aside = [c for c in considered if c.verdict == "set_aside"]
        summary = f"It appears in {len(sources)} of your sources, linked to {len(considered)} responsibilities. We checked each link."
        if only_route:
            summary += " Nothing else works yet to " + join_and(only_route) + "."
        if only_reminder:
            summary += " It's the only reminder to " + join_and(only_reminder) + "."
        if set_aside:
            summary += " Set aside: " + " ".join(c.message for c in set_aside)
        path = [PathNode("person", scenario.leaver, f"{_name(world, scenario.leaver)} leaves on {_fmt(scenario.start)}")]
        for a in scenario.assumptions:
            if a.target == rid:
                path.append(PathNode("assumption", a.id, a.label, claim_ids=a.claim_ids))
        path.append(PathNode("resource", rid, res.label, claim_ids=res.claim_ids))
        for c in retained:
            r = base.results[c.responsibility]
            path.append(PathNode("responsibility", c.responsibility, r.label, r.state.value))
        dates = sorted({base.results[c.responsibility].first_problem for c in retained if base.results[c.responsibility].first_problem})
        severity = max(SEVERITY[base.results[c.responsibility].state] for c in retained)
        noun = "thing" if len(retained) == 1 else "things"
        out.append(
            Finding(
                id=f"shared:{rid}",
                kind="SHARED_DEPENDENCY",
                title=f"{cap(res.label)} is still needed for {len(retained)} {noun} during the absence",
                summary=summary,
                severity=severity,
                responsibilities=[c.responsibility for c in retained],
                dates=dates,
                path=path,
                claim_ids=claim_ids,
                considered=considered,
                assumptions=assumption_ids,
            )
        )
    return out


def _classify(
    world: World,
    scenario: Scenario,
    ev: Evaluator,
    resp: Responsibility,
    b: ResponsibilityResult,
    c: ResponsibilityResult,
    rid: str,
) -> Considered:
    """Decide whether a link between a resource and a responsibility really matters.

    retained / ONLY_ROUTE     the resource blocks it and nothing else works yet
    retained / ONLY_REMINDER  it's the only way anyone at home learns the dates
    set_aside / OTHER_ROUTE_WORKS, OTHER_REMINDER, STILL_REACHABLE, MENTIONED_ONLY
    """
    res = world.resources[rid]
    # A route link only matters if some route actually needs the resource; a
    # resource that is only the reminder is judged on the reminder alone.
    route_link = any(route_depends_on(world, r, rid) for r in resp.routes)
    if route_link:
        independent_routes = [r for r in resp.routes if not route_depends_on(world, r, rid)]
        for route in independent_routes:
            v = _best_route_value(world, b, route)
            if v in (Tri.T, Tri.U):
                return Considered(
                    resp.id,
                    "set_aside",
                    "OTHER_ROUTE_WORKS",
                    f"{cap(resp.label)}: there's another way that doesn't need it ({route.label}).",
                    route.claim_ids,
                )
    hard = _reasons_mention(b.reasons, rid)
    improved = SEVERITY[c.state] < SEVERITY[b.state] or c.coverage > b.coverage
    if hard and improved:
        return Considered(resp.id, "retained", "ONLY_ROUTE", f"Nothing else works yet to {resp.label}.", res.claim_ids)
    reminder_sources = [s for s in resp.awareness_sources if _reaches(world, s, rid, set())]
    if reminder_sources:
        others = [s for s in resp.awareness_sources if not _reaches(world, s, rid, set())]
        if others:
            other_label = world.resources[others[0]].label if others[0] in world.resources else others[0]
            claims = world.resources[others[0]].claim_ids if others[0] in world.resources else ()
            return Considered(resp.id, "set_aside", "OTHER_REMINDER", f"{cap(resp.label)}: the dates are also in {other_label}.", claims)
        day = b.occurrences[0].date if b.occurrences else scenario.start
        at_home = [
            pid for pid, p in world.people.items() if pid != scenario.leaver and not p.minor and not scenario.person_absent(pid, day)
        ]
        if any(ev.access(src, pid, day)[0] is Tri.T for src in reminder_sources for pid in at_home):
            return Considered(resp.id, "set_aside", "STILL_REACHABLE", f"{cap(resp.label)}: someone at home still gets the reminder.", ())
        return Considered(resp.id, "retained", "ONLY_REMINDER", f"It's the only reminder to {resp.label}.", res.claim_ids)
    if hard:
        return Considered(resp.id, "retained", "ONLY_ROUTE", f"{cap(resp.label)} can't be done without it.", res.claim_ids)
    return Considered(resp.id, "set_aside", "MENTIONED_ONLY", f"{cap(resp.label)}: it's only mentioned, not needed.", ())


def held_by_leaver_findings(world: World, scenario: Scenario, base: ScenarioResult) -> list[Finding]:
    """Things only the leaver has, knows or can use, that a stand-in would need.

    We don't only look at the people already recorded for a responsibility: we
    ask what *any* adult at home would hit if they tried each route, because the
    point is to find what nobody has said yet. A held item is reported only when
    no route that avoids it could work."""
    ev = Evaluator(world, scenario)
    leaver = scenario.leaver
    # container -> item -> responsibilities
    held: dict[str, dict[str, set[str]]] = {}
    first_dates: dict[str, date] = {}
    for resp_id, r in sorted(base.results.items()):
        if r.state.ready:
            continue
        resp = world.responsibilities[resp_id]
        stand_ins = stand_ins_for(world, scenario, resp)
        # Every date that isn't ready yet: another route may cover the first dates
        # and stop working later (an ID that expires mid-absence, say).
        for occ in (o for o in r.occurrences if not o.prepared):
            per_route: dict[str, list] = {}
            for route in resp.routes:
                per_route[route.id] = [ev.option(resp, route, pid, occ.date) for pid in stand_ins]
            for route in resp.routes:
                for opt in per_route[route.id]:
                    for reason in opt.reasons:
                        if reason.code != "HOLDER_AWAY" or reason.refs.get("holder") != leaver:
                            continue
                        container = reason.refs["resource"]
                        item = reason.refs.get("item", container)
                        # skip if a route that avoids this container could work for someone
                        avoid = [rt for rt in resp.routes if not _reaches_route(world, rt, container)]
                        if any(o.value in (Tri.T, Tri.U) for rt in avoid for o in per_route[rt.id]):
                            continue
                        held.setdefault(container, {}).setdefault(item, set()).add(resp_id)
                        first_dates[resp_id] = min(first_dates.get(resp_id, occ.date), occ.date)
    groups: dict[str, list[str]] = {"contact": [], "location": [], "other": []}

    def first(resp_ids: set[str]) -> date:
        return min(first_dates[x] for x in resp_ids)

    for container in sorted(held, key=lambda c: (min(first(v) for v in held[c].values()), c)):
        kind = world.resources[container].kind.value
        groups["contact" if kind in ("handset", "contact") else "location" if kind == "location" else "other"].append(container)
    name = _name(world, leaver)
    titles = {
        "contact": f"Some contacts are only on {name}'s phone",
        "location": f"Only {name} knows where some things are kept",
        "other": f"Some things only {name} can use",
    }
    out: list[Finding] = []
    for group, containers in groups.items():
        if not containers:
            continue
        resp_ids = sorted({x for c in containers for items in held[c].values() for x in items})
        path = [PathNode("person", leaver, f"{name} leaves on {_fmt(scenario.start)}")]
        claim_ids: set[str] = set()
        sentences = []
        other_by_need: dict[str, list[str]] = {}
        for c in containers:
            cres = world.resources[c]
            claim_ids |= set(cres.claim_ids)
            parts = []
            for item_id in sorted(held[c], key=lambda i: (first(held[c][i]), i)):
                item = world.resources.get(item_id, cres)
                claim_ids |= set(item.claim_ids)
                needed = join_and([world.responsibilities[x].label for x in sorted(held[c][item_id])])
                if item_id == c:
                    parts.append((cres.label, needed))
                elif group == "other":
                    parts.append((f"{item.label} (only in {cres.label})", needed))
                else:
                    parts.append((item.label, needed))
                path.append(
                    PathNode("resource", item_id, item.label if item_id == c else f"{item.label} ({cres.label})", claim_ids=item.claim_ids)
                )
            if group == "contact":
                body = "; ".join(f"{label}, needed to {needed}" for label, needed in parts)
                many = {1: "It's", 2: "Both are"}.get(len(parts), "All are")
                sentences.append(f"{cap(body)}. {many} only on {cres.label}.")
            elif group == "location":
                items = join_and([label for label, _ in parts])
                needed = join_and(sorted({n for _, n in parts}))
                sentences.append(f"{cap(items)}, needed to {needed}: kept in {cres.label}.")
            else:
                for label, needed in parts:
                    other_by_need.setdefault(needed, []).append(label)
        for needed, labels in other_by_need.items():
            sentences.append(f"{cap(join_and(labels))}, needed to {needed}.")
        for x in resp_ids:
            path.append(PathNode("responsibility", x, base.results[x].label, base.results[x].state.value))
        out.append(
            Finding(
                id=f"held:{group}",
                kind="HELD_BY_LEAVER",
                title=titles[group],
                summary=" ".join(sentences),
                severity=max(SEVERITY[base.results[x].state] for x in resp_ids),
                responsibilities=resp_ids,
                dates=sorted({first_dates[x] for x in resp_ids}),
                path=path,
                claim_ids=sorted(claim_ids),
            )
        )
    return out


def stand_ins_for(world: World, scenario: Scenario, resp: Responsibility) -> list[str]:
    """People who could plausibly take this on: those already recorded for it,
    plus the household's named backup. Never the leaver, never a child."""
    names: list[str] = []
    for route in resp.routes:
        for pid in world.candidates(resp, route):
            if pid not in names:
                names.append(pid)
    for pid, person in sorted(world.people.items()):
        if person.role == "backup" and pid not in names:
            names.append(pid)
    return [pid for pid in names if pid != scenario.leaver and pid in world.people and not world.people[pid].minor]


def _reaches_route(world: World, route: Route, rid: str) -> bool:
    return any(_reaches(world, req.target, rid, set()) for req in route.requirements)


def _held_label(world: World, rid: str) -> str:
    """Name the thing a person actually needs, not the container: for a handset,
    the contacts stored on it; for a location, the items kept there."""
    res = world.resources[rid]
    kind = res.kind.value
    if kind in ("handset", "location"):
        inside = [r.label for r in world.resources.values() if rid in r.stored_on]
        if inside:
            return f"{join_and(inside)} ({res.label})"
    return res.label


def schedule_clash_findings(world: World, scenario: Scenario, base: ScenarioResult) -> list[Finding]:
    clashes: dict[tuple[str, str], list[tuple[str, date]]] = {}
    claims: dict[tuple[str, str], tuple[str, ...]] = {}
    for resp_id, r in base.results.items():
        for occ in r.occurrences:
            if occ.value is not Tri.F:
                continue
            for reason in occ.reasons:
                if reason.code == "BUSY":
                    key = (reason.refs["person"], reason.refs["commitment"])
                    clashes.setdefault(key, []).append((resp_id, occ.date))
                    claims[key] = reason.claim_ids
    out = []
    for (person, cid), items in sorted(clashes.items()):
        commitment = next((c for c in world.commitments if c.id == cid), None)
        resp_ids = sorted({x for x, _ in items})
        dates = sorted({d for _, d in items})
        parts = []
        for x in resp_ids:
            ds = [d for y, d in items if y == x]
            if len(ds) == 1:
                parts.append(f"{world.responsibilities[x].label} on {_fmt(ds[0])}")
            else:
                parts.append(f"{world.responsibilities[x].label} ({len(ds)} dates)")
        label = commitment.label if commitment else cid
        path = [
            PathNode(
                "commitment",
                cid,
                f"{_name(world, person)}: {label}" + (f", {commitment.window.label()}" if commitment else ""),
                claim_ids=claims[(person, cid)],
            )
        ]
        for x in resp_ids:
            path.append(PathNode("responsibility", x, base.results[x].label, base.results[x].state.value))
        out.append(
            Finding(
                id=f"clash:{person}:{cid}",
                kind="SCHEDULE_CLASH",
                title=f"{_name(world, person)} is busy with {label} when {len(resp_ids)} {'thing needs' if len(resp_ids) == 1 else 'things need'} doing",
                summary=_clash_summary(world, person, commitment, label, parts),
                severity=max(SEVERITY[base.results[x].state] for x in resp_ids),
                responsibilities=resp_ids,
                dates=dates,
                path=path,
                claim_ids=list(claims[(person, cid)]),
            )
        )
    return out


def _clash_summary(world: World, person: str, commitment, label: str, parts: list[str]) -> str:
    who = _name(world, person)
    if commitment is None:
        return f"{who} is busy ({label}). That clashes with: {join_and(parts)}."
    rec = commitment.recurrence
    when = f"on {fmt_day(rec.anchor)}" if rec.freq.value == "once" and rec.anchor else rec.label()
    text = f"{who} is busy {when}, {commitment.window.label()}, for {label}. That clashes with: {join_and(parts)}."
    if not commitment.movable:
        text += " It's booked and can't be moved."
    return text


def deadline_findings(world: World, scenario: Scenario, base: ScenarioResult) -> list[Finding]:
    out = []
    for rid, res in sorted(world.resources.items()):
        if not res.valid_until or not (res.valid_until < scenario.end):
            continue
        before = res.valid_until < scenario.start
        dependents = []
        for resp_id, r in base.results.items():
            resp = world.responsibilities[resp_id]
            if any(req.kind is ReqKind.VALID and req.target == rid for route in resp.routes for req in route.requirements):
                if not r.state.ready:
                    dependents.append(resp_id)
        renewal = res.renewed_by if res.renewed_by in base.results else None
        affected = ([renewal] if renewal and not base.results[renewal].state.ready else []) + dependents
        if not affected:
            continue
        expiry = _fmt(res.valid_until)
        path = [PathNode("resource", rid, f"{res.label}: valid until {expiry}", claim_ids=res.claim_ids)]
        if before:
            path.append(PathNode("person", scenario.leaver, f"{_name(world, scenario.leaver)} leaves on {_fmt(scenario.start)}"))
        if renewal:
            rr = base.results[renewal]
            path.append(PathNode("responsibility", renewal, rr.label, rr.state.value))
        for d in dependents:
            dr = base.results[d]
            path.append(PathNode("responsibility", d, dr.label, dr.state.value))
        summary = (
            f"It expires on {expiry}, during the absence."
            if not before
            else f"It expires on {expiry}, before {_name(world, scenario.leaver)} leaves. Renew it before leaving."
        )
        if renewal and not before and not base.results[renewal].state.ready:
            summary += f" Nobody at home is ready to {base.results[renewal].label}."
        blocks = {d: _first_blocked_after(base.results[d], res.valid_until) for d in dependents}
        if dependents:
            summary += " " + " ".join(f"From {_fmt(day)}, this blocks: {base.results[d].label}." for d, day in blocks.items() if day)
        dates = sorted({res.valid_until} | {day for day in blocks.values() if day})
        out.append(
            Finding(
                id=f"deadline:{rid}",
                kind="DEADLINE_IN_ABSENCE" if not before else "DEADLINE_BEFORE_DEPARTURE",
                title=f"{cap(res.label)} expires during the absence"
                if not before
                else f"{cap(res.label)} expires before {_name(world, scenario.leaver)} leaves",
                summary=summary,
                severity=max(SEVERITY[base.results[x].state] for x in affected),
                responsibilities=affected,
                dates=dates,
                path=path,
                claim_ids=list(res.claim_ids),
            )
        )
    return out


def _first_blocked_after(r: ResponsibilityResult, expiry: date) -> date | None:
    """The first date, after something expires, that this responsibility stops working."""
    after = [o for o in r.occurrences if o.date > expiry]
    hit = next((o.date for o in after if o.value is Tri.F), None) or next((o.date for o in after if o.value is not Tri.T), None)
    return hit or r.first_problem


def not_asked_findings(world: World, scenario: Scenario, base: ScenarioResult) -> list[Finding]:
    asks: dict[tuple[str, str], date] = {}
    for resp_id, r in base.results.items():
        for occ in r.occurrences:
            for o in occ.options:
                if any(reason.code == "WILLINGNESS_UNKNOWN" for reason in o.reasons):
                    key = (o.person, resp_id)
                    asks[key] = min(asks.get(key, occ.date), occ.date)
    if not asks:
        return []
    questions = []
    path = []
    pairs = []
    for (person, resp_id), _ in sorted(asks.items()):
        label = world.responsibilities[resp_id].label
        question = f"Ask {_name(world, person)}: can you {label}?"
        questions.append(question)
        pairs.append({"person": person, "responsibility": resp_id, "question": question})
        path.append(PathNode("person", person, f"{_name(world, person)} hasn't been asked about: {label}"))
    resp_ids = sorted({r for _, r in asks})
    return [
        Finding(
            id="ask:willingness",
            kind="NOT_ASKED",
            title="A few people haven't been asked yet",
            summary=" ".join(questions),
            severity=max(SEVERITY[base.results[x].state] for x in resp_ids),
            responsibilities=resp_ids,
            dates=sorted(set(asks.values())),
            path=path,
            claim_ids=sorted({c for (p, r) in asks for c in world.willingness_claims.get((p, r), ())}),
            questions=questions,
            asks=pairs,
        )
    ]


def contradiction_findings(world: World, contradictions: list[Contradiction]) -> list[Finding]:
    out = []
    for c in contradictions:
        values = " or ".join(f"'{v}'" for v, _ in c.values)
        out.append(
            Finding(
                id=f"conflict:{c.id}",
                kind="CONTRADICTION",
                title=f"Two sources disagree: {c.label}",
                summary=f"Your sources say {values}. Which is right?",
                severity=3,
                responsibilities=[c.responsibility] if c.responsibility else [],
                dates=[],
                path=[PathNode("fact", c.id, c.label)],
                claim_ids=[cid for _, cid in c.values],
                questions=[f"Which is right for {c.label}: {values}?"],
            )
        )
    return out


def _rank(world: World, base: ScenarioResult, f: Finding, scenario: Scenario) -> float:
    weight = max((world.responsibilities[r].weight for r in f.responsibilities if r in world.responsibilities), default=1)
    urgency = 0.0
    if f.dates:
        days = (min(f.dates) - scenario.start).days
        urgency = max(0.0, 30 - days) / 30
    breadth = len(f.responsibilities)
    return f.severity * 10 + weight * 3 + breadth + urgency * 5 + (2 if f.kind == "SHARED_DEPENDENCY" else 0)
