"""Scenario evaluation: can the recorded routes keep each responsibility going?

Two layers are kept separate:
  * route feasibility (T/F/U) - can a willing, present person complete a recorded
    route with what it needs, on the dates it is due?
  * handover readiness - has the evidence policy for that responsibility been met
    (dates known, instructions explained back, key step shown)?
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum

from .model import (
    ENGINE_VERSION,
    POLICY_VERSION,
    Policy,
    Practical,
    ReqKind,
    Resource,
    ResourceKind,
    Responsibility,
    Route,
    Scenario,
    Understanding,
    World,
)
from .text import cap, fmt_date, fmt_day
from .timeutil import commitments_on, occurrence_dates, unavailable_on
from .tri import Tri, t_and, t_or, worst

ALLOCATION_NODE_LIMIT = 100_000


class State(str, Enum):
    PREPARED = "prepared"
    NEEDS_HANDOVER = "needs_handover"
    NEEDS_CONFIRMATION = "needs_confirmation"
    BLOCKED = "blocked"
    NOT_DUE = "not_due"

    @property
    def ready(self) -> bool:
        return self in (State.PREPARED, State.NOT_DUE)


SEVERITY = {
    State.BLOCKED: 4,
    State.NEEDS_CONFIRMATION: 3,
    State.NEEDS_HANDOVER: 2,
    State.PREPARED: 1,
    State.NOT_DUE: 0,
}


@dataclass
class Reason:
    code: str
    message: str
    refs: dict[str, str] = field(default_factory=dict)
    claim_ids: tuple[str, ...] = ()
    kind: str = "hard"  # hard (blocks) | unknown (needs confirmation) | info

    def key(self) -> tuple:
        return (self.code, tuple(sorted(self.refs.items())))


@dataclass
class OptionResult:
    route_id: str
    person: str
    value: Tri
    reasons: list[Reason]
    day: date
    window_label: str | None = None
    policy_missing: list[str] = field(default_factory=list)


@dataclass
class OccurrenceResult:
    date: date
    act_by: date
    value: Tri
    options: list[OptionResult]
    chosen: OptionResult | None
    reasons: list[Reason]

    @property
    def prepared(self) -> bool:
        return self.value is Tri.T and self.chosen is not None and not self.chosen.policy_missing


@dataclass
class ResponsibilityResult:
    id: str
    label: str
    weight: int
    state: State
    feasibility: Tri
    occurrences: list[OccurrenceResult]
    first_problem: date | None
    performers: list[str]
    missing: dict[str, list[str]]
    reasons: list[Reason]

    @property
    def coverage(self) -> float:
        """Share of dated occurrences that are fully prepared (1.0 when nothing is due)."""
        if not self.occurrences:
            return 1.0
        return sum(1 for o in self.occurrences if o.prepared) / len(self.occurrences)


@dataclass
class Summary:
    total: int
    ready: int
    prepared: int
    not_due: int
    needs_handover: int
    needs_confirmation: int
    blocked: int
    weight_total: int
    weight_ready: int
    occurrence_coverage: float  # weighted share of prepared occurrences (optimisation target)

    @property
    def ready_pct(self) -> float | None:
        if self.weight_total == 0:
            return None
        return round(100.0 * self.weight_ready / self.weight_total, 1)


@dataclass
class ScenarioResult:
    scenario_id: str
    world_version: int
    engine_version: str
    policy_version: str
    results: dict[str, ResponsibilityResult]
    summary: Summary
    diagnostics: list[str]


class Evaluator:
    """Evaluates a World under a Scenario. Pure and deterministic."""

    def __init__(self, world: World, scenario: Scenario):
        self.world = world
        self.scenario = scenario
        self._occ_cache: dict[str, list[OccurrenceResult]] = {}
        self._in_progress: set[str] = set()
        self.diagnostics: list[str] = []

    # ------------------------------------------------------------------ resources

    def access(
        self, rid: str, person: str, day: date, path: frozenset[str] = frozenset(), via: Resource | None = None
    ) -> tuple[Tri, list[Reason]]:
        """Can `person` use resource `rid` on `day`? `via` is the item being looked
        for when `rid` is a container (a contact on a phone, a book in a drawer)."""
        w, s = self.world, self.scenario
        if rid in path:
            self.diagnostics.append(f"cycle while resolving {rid}")
            return Tri.U, [Reason("CYCLE", f"A loop was found while checking {rid}.", {"resource": rid}, kind="unknown")]
        res = w.resources.get(rid)
        if res is None:
            return Tri.U, [Reason("UNKNOWN_RESOURCE", f"We don't know what '{rid}' is.", {"resource": rid}, kind="unknown")]
        assumption = s.resource_unavailable(rid, day)
        if assumption:
            return Tri.F, [
                Reason(
                    "SCENARIO_UNAVAILABLE",
                    f"{cap(res.label)} won't be in use during the absence.",
                    {"resource": rid, "assumption": assumption.id},
                    assumption.claim_ids + res.claim_ids,
                )
            ]
        values: list[Tri] = []
        reasons: list[Reason] = []
        # Someone who holds the thing, or was given their own copy, doesn't need the
        # container it is kept in (a number saved on their own phone, say).
        own = res.holder == person or person in res.shared_with
        if not res.generic and res.holder and not own:
            holder = w.people.get(res.holder)
            holder_name = holder.name if holder else res.holder
            refs = {"resource": rid, "holder": res.holder}
            if via is not None:
                refs["item"] = via.id
            claim_ids = tuple(dict.fromkeys(res.claim_ids + (via.claim_ids if via else ())))
            if s.person_absent(res.holder, day):
                values.append(Tri.F)
                reasons.append(Reason("HOLDER_AWAY", _holder_message(res, holder_name, via, away=True), refs, claim_ids))
            else:
                values.append(Tri.U)
                reasons.append(Reason("NEEDS_HOLDER", _holder_message(res, holder_name, via, away=False), refs, claim_ids, kind="unknown"))
        if res.stored_on and not own:
            sub = [self.access(c, person, day, path | {rid}, via=res) for c in res.stored_on]
            stored_value = t_or(v for v, _ in sub)
            values.append(stored_value)
            if stored_value is not Tri.T:
                for v, rs in sub:
                    if v is not Tri.T:
                        reasons.extend(rs)
        for prerequisite in res.requires:
            v, rs = self.access(prerequisite, person, day, path | {rid})
            values.append(v)
            if v is not Tri.T:
                reasons.extend(rs)
        return t_and(values), reasons

    def validity(self, rid: str, day: date) -> tuple[Tri, list[Reason]]:
        res = self.world.resources.get(rid)
        if res is None:
            return Tri.U, [Reason("UNKNOWN_RESOURCE", f"We don't know what '{rid}' is.", {"resource": rid}, kind="unknown")]
        if res.valid_until is None:
            return Tri.U, [
                Reason(
                    "VALIDITY_UNKNOWN", f"We don't know until when {res.label} is valid.", {"resource": rid}, res.claim_ids, kind="unknown"
                )
            ]
        if day <= res.valid_until:
            return Tri.T, []
        expiry = fmt_date(res.valid_until)
        if not res.renewed_by or res.renewed_by not in self.world.responsibilities:
            return Tri.F, [
                Reason("EXPIRED", f"{cap(res.label)} expires on {expiry} and no renewal is recorded.", {"resource": rid}, res.claim_ids)
            ]
        renewal = self.state_of(res.renewed_by)
        renewal_label = self.world.responsibilities[res.renewed_by].label
        if renewal is None:
            return Tri.U, [Reason("CYCLE", f"Checking {res.label} depends on itself.", {"resource": rid}, kind="unknown")]
        if renewal.state is State.PREPARED:
            return Tri.T, [
                Reason(
                    "PROJECTED_RENEWAL",
                    f"{cap(res.label)} expires on {expiry}; it stays valid only if the prepared renewal is done.",
                    {"resource": rid, "responsibility": res.renewed_by},
                    res.claim_ids,
                    kind="info",
                )
            ]
        if renewal.state is State.NOT_DUE and res.valid_until < self.scenario.start:
            # the renewal fell due before the absence: only the leaver can do it, before leaving
            return Tri.F, [
                Reason(
                    "EXPIRES_BEFORE_ABSENCE",
                    f"{cap(res.label)} expires on {expiry}, before the absence starts. Renew it before leaving.",
                    {"resource": rid, "responsibility": res.renewed_by},
                    res.claim_ids,
                )
            ]
        if renewal.state is State.BLOCKED:
            return Tri.F, [
                Reason(
                    "EXPIRES_NOT_RENEWABLE",
                    f"{cap(res.label)} expires on {expiry}, and nobody at home can {renewal_label} yet.",
                    {"resource": rid, "responsibility": res.renewed_by},
                    res.claim_ids,
                )
            ]
        return Tri.U, [
            Reason(
                "RENEWAL_NOT_READY",
                f"{cap(res.label)} expires on {expiry}, and nobody is fully ready to {renewal_label} yet.",
                {"resource": rid, "responsibility": res.renewed_by},
                res.claim_ids,
                kind="unknown",
            )
        ]

    def fact(self, fid: str) -> tuple[Tri, list[Reason]]:
        value = self.world.facts.get(fid, Tri.U)
        label = self.world.fact_labels.get(fid, fid)
        claims = self.world.fact_claims.get(fid, ())
        if value is Tri.T:
            return Tri.T, []
        if value is Tri.F:
            return Tri.F, [Reason("FACT_FALSE", f"Not true yet: {label}.", {"fact": fid}, claims)]
        return Tri.U, [Reason("FACT_UNKNOWN", f"Not confirmed yet: {label}.", {"fact": fid}, claims, kind="unknown")]

    # ------------------------------------------------------------------ performers

    def performer(self, resp: Responsibility, route: Route, person: str, due: date) -> tuple[Tri, list[Reason], date]:
        w = self.world
        p = w.people.get(person)
        if p is None:
            return Tri.U, [Reason("UNKNOWN_PERSON", f"We don't know who '{person}' is.", {"person": person}, kind="unknown")], due
        if p.minor:
            return Tri.F, [Reason("MINOR", f"{p.name} is a child and isn't given this responsibility.", {"person": person})], due
        owner = w.is_owner(person, resp.id)
        willing = Tri.T if owner else w.willingness.get((person, resp.id), Tri.U)
        willing_claims = w.willingness_claims.get((person, resp.id), ())
        if willing is Tri.F:
            return Tri.F, [Reason("NOT_WILLING", f"{p.name} has said they can't take this on.", {"person": person}, willing_claims)], due

        reasons: list[Reason] = []
        candidate_days = [due - timedelta(days=k) for k in range(0, route.flexible_days + 1)]
        feasible_day: date | None = None
        for day in candidate_days:
            day_reasons = self._day_blockers(route, person, day)
            if not day_reasons:
                feasible_day = day
                break
            if day == due:
                reasons.extend(day_reasons)
        if feasible_day is None:
            if route.flexible_days and not reasons:
                reasons.append(Reason("NO_FREE_DAY", f"{p.name} has no free time for this before it's due.", {"person": person}))
            return Tri.F, reasons, due
        if willing is Tri.U:
            return (
                Tri.U,
                [
                    Reason(
                        "WILLINGNESS_UNKNOWN",
                        f"{p.name} hasn't been asked yet.",
                        {"person": person, "responsibility": resp.id},
                        kind="unknown",
                    )
                ],
                feasible_day,
            )
        return Tri.T, [], feasible_day

    def _day_blockers(self, route: Route, person: str, day: date) -> list[Reason]:
        w, s = self.world, self.scenario
        p = w.people[person]
        if s.person_absent(person, day):
            return [Reason("PERFORMER_AWAY", f"{p.name} is away.", {"person": person})]
        blockers: list[Reason] = []
        for u in unavailable_on(w, person, day):
            blockers.append(
                Reason(
                    "UNAVAILABLE_ON_DATE",
                    f"{p.name} isn't available on {fmt_day(day)}: {u.label}.",
                    {"person": person, "date": day.isoformat()},
                    u.claim_ids,
                )
            )
        if route.weekdays is not None and day.weekday() not in route.weekdays:
            blockers.append(Reason("WEEKDAY_CLOSED", f"Not possible on a {day.strftime('%A')}.", {"date": day.isoformat()}))
        if route.window is not None:
            for c in commitments_on(w, person, day):
                if c.window.overlaps(route.window):
                    blockers.append(
                        Reason(
                            "BUSY",
                            f"{p.name} is busy on {fmt_day(day)} ({c.label}, {c.window.label()}), and this needs {route.window.label()}.",
                            {"person": person, "commitment": c.id, "date": day.isoformat(), "movable": "yes" if c.movable else "no"},
                            c.claim_ids,
                        )
                    )
        return blockers

    # ------------------------------------------------------------------ policy

    def aware(self, resp: Responsibility, person: str, day: date) -> bool:
        if resp.id in self.world.card_entries:
            return True
        return any(self.access(src, person, day)[0] is Tri.T for src in resp.awareness_sources)

    def policy_missing(self, resp: Responsibility, person: str, day: date) -> list[str]:
        if self.world.is_owner(person, resp.id):
            return []
        record = self.world.handover(person, resp.id)
        missing: list[str] = []
        if resp.awareness_required and not self.aware(resp, person, day):
            missing.append("KNOWS_WHEN")
        if resp.policy is Policy.LIGHT:
            if record.understanding < Understanding.VIEWED:
                missing.append("VIEW")
        else:
            if record.understanding < Understanding.UNASSISTED:
                missing.append("EXPLAIN")
        if resp.policy is Policy.CRITICAL and resp.demo_step and record.practical < Practical.WITNESSED:
            missing.append("SHOW")
        return missing

    # ------------------------------------------------------------------ occurrences

    def requirement(self, req, person: str, day: date) -> tuple[Tri, list[Reason]]:
        if req.kind is ReqKind.ACCESS:
            return self.access(req.target, person, day)
        if req.kind is ReqKind.VALID:
            return self.validity(req.target, day)
        return self.fact(req.target)

    def option(self, resp: Responsibility, route: Route, person: str, due: date) -> OptionResult:
        pv, preasons, day = self.performer(resp, route, person, due)
        values = [pv]
        reasons = list(preasons)
        if not route.requirements_known:
            values.append(Tri.U)
            reasons.append(
                Reason("REQUIREMENTS_UNKNOWN", f"We don't know yet what '{route.label}' needs.", {"route": route.id}, kind="unknown")
            )
        for req in route.requirements:
            v, rs = self.requirement(req, person, day)
            values.append(v)
            if v is not Tri.T:
                reasons.extend(rs)
            else:
                reasons.extend(r for r in rs if r.kind == "info")
        value = t_and(values)
        missing = self.policy_missing(resp, person, day) if value is Tri.T else []
        return OptionResult(route.id, person, value, reasons, day, route.window.label() if route.window else None, missing)

    def occurrence(self, resp: Responsibility, due: date) -> OccurrenceResult:
        options: list[OptionResult] = []
        for route in resp.routes:
            people = self.world.candidates(resp, route)
            if not people:
                options.append(
                    OptionResult(
                        route.id,
                        "",
                        Tri.U,
                        [Reason("NO_PERFORMER", f"Nobody is recorded for '{route.label}'.", {"route": route.id}, kind="unknown")],
                        due,
                    )
                )
            for person in people:
                options.append(self.option(resp, route, person, due))
        if not resp.routes:
            value = Tri.U
            reasons = [Reason("NO_ROUTE", f"No way of doing '{resp.label}' is recorded yet.", {"responsibility": resp.id}, kind="unknown")]
        else:
            value = t_or(o.value for o in options)
            reasons = _failure_reasons(options) if value is not Tri.T else []
        chosen = _choose(options, self.world, resp)
        return OccurrenceResult(due, due - timedelta(days=resp.lead_days), value, options, chosen, reasons)

    def occurrences(self, rid: str) -> list[OccurrenceResult] | None:
        if rid in self._occ_cache:
            return self._occ_cache[rid]
        if rid in self._in_progress:
            return None
        self._in_progress.add(rid)
        try:
            resp = self.world.responsibilities[rid]
            occs = [self.occurrence(resp, d) for d in occurrence_dates(self.world, self.scenario, resp)]
        finally:
            self._in_progress.discard(rid)
        self._occ_cache[rid] = occs
        return occs

    def state_of(self, rid: str) -> ResponsibilityResult | None:
        occs = self.occurrences(rid)
        if occs is None:
            return None
        return _result(self.world.responsibilities[rid], occs)

    # ------------------------------------------------------------------ allocation

    def allocate(self) -> None:
        """Jointly allocate fixed-time occurrences so one person is never in two
        places at once. Occurrences that individually work but lose in the joint
        plan become F with a CAPACITY_CONFLICT reason (a planning trade-off)."""
        by_day: dict[date, list[tuple[Responsibility, OccurrenceResult]]] = {}
        for rid, occs in self._occ_cache.items():
            resp = self.world.responsibilities[rid]
            for occ in occs:
                if occ.value is Tri.T and occ.chosen is not None:
                    route = _route(resp, occ.chosen.route_id)
                    if route and route.window is not None and route.flexible_days == 0:
                        by_day.setdefault(occ.chosen.day, []).append((resp, occ))
        for day, items in sorted(by_day.items()):
            if len(items) < 2:
                continue
            if not _has_conflict(items, self.world):
                continue
            self._solve_day(day, items)

    def _solve_day(self, day: date, items) -> None:
        items = sorted(items, key=lambda it: (-it[0].weight, it[0].id))
        choices = []
        for resp, occ in items:
            opts = [o for o in occ.options if o.value is Tri.T and _route(resp, o.route_id).window is not None]
            opts.sort(key=lambda o: _option_rank(o, self.world, resp))
            choices.append(opts)

        best: dict = {"score": -1, "assign": None}
        nodes = 0
        incomplete = False

        def windows_clash(assign, k, opt):
            route_k = _route(items[k][0], opt.route_id)
            for j, other in enumerate(assign):
                if other is None:
                    continue
                route_j = _route(items[j][0], other.route_id)
                if other.person == opt.person and other.day == opt.day and route_j.window.overlaps(route_k.window):
                    return True
            return False

        def search(k, assign, score):
            nonlocal nodes, incomplete
            nodes += 1
            if nodes > ALLOCATION_NODE_LIMIT:
                incomplete = True
                return
            if k == len(items):
                if score > best["score"]:
                    best["score"], best["assign"] = score, list(assign)
                return
            remaining = sum(items[j][0].weight for j in range(k, len(items)))
            if score + remaining <= best["score"]:
                return
            for opt in choices[k]:
                if not windows_clash(assign, k, opt):
                    assign.append(opt)
                    search(k + 1, assign, score + items[k][0].weight)
                    assign.pop()
            assign.append(None)
            search(k + 1, assign, score)
            assign.pop()

        search(0, [], 0)
        if incomplete:
            self.diagnostics.append(f"allocation search limit reached on {day.isoformat()}")
            for _, occ in items:
                occ.value = Tri.U
                occ.reasons = [
                    Reason(
                        "ALLOCATION_INCOMPLETE",
                        "We couldn't finish checking who can do what on this day.",
                        {"date": day.isoformat()},
                        kind="unknown",
                    )
                ]
            return
        assign = best["assign"] or [None] * len(items)
        for (_resp, occ), opt in zip(items, assign, strict=False):
            if opt is None:
                winners = [items[j][0].label for j, o in enumerate(assign) if o is not None]
                occ.value = Tri.F
                occ.chosen = None
                occ.reasons = [
                    Reason(
                        "CAPACITY_CONFLICT",
                        f"On {fmt_day(day)} the same people are needed for: {', '.join(winners)}.",
                        {"date": day.isoformat()},
                    )
                ]
            else:
                occ.chosen = opt

    # ------------------------------------------------------------------ public

    def run(self) -> ScenarioResult:
        world = self.world
        for rid, resp in sorted(world.responsibilities.items()):
            if resp.in_scope:
                self.occurrences(rid)
        self.allocate()
        results = {
            rid: _result(world.responsibilities[rid], occs)
            for rid, occs in sorted(self._occ_cache.items())
            if world.responsibilities[rid].in_scope
        }
        return ScenarioResult(
            scenario_id=self.scenario.id,
            world_version=world.version,
            engine_version=ENGINE_VERSION,
            policy_version=POLICY_VERSION,
            results=results,
            summary=summarise(results),
            diagnostics=list(dict.fromkeys(self.diagnostics)),
        )


# ---------------------------------------------------------------------- helpers


def evaluate(world: World, scenario: Scenario) -> ScenarioResult:
    return Evaluator(world, scenario).run()


def _route(resp: Responsibility, route_id: str) -> Route | None:
    for r in resp.routes:
        if r.id == route_id:
            return r
    return None


def _option_rank(o: OptionResult, world: World, resp: Responsibility) -> tuple:
    route_index = next((i for i, r in enumerate(resp.routes) if r.id == o.route_id), 99)
    return (
        len(o.policy_missing),
        0 if world.is_owner(o.person, resp.id) else 1,
        route_index,
        o.person,
    )


def _choose(options: list[OptionResult], world: World, resp: Responsibility) -> OptionResult | None:
    working = [o for o in options if o.value is Tri.T]
    if not working:
        return None
    return sorted(working, key=lambda o: _option_rank(o, world, resp))[0]


def _failure_reasons(options: list[OptionResult]) -> list[Reason]:
    seen: dict[tuple, Reason] = {}
    for o in options:
        for r in o.reasons:
            if r.kind == "info":
                continue
            seen.setdefault(r.key(), r)
    return list(seen.values())


def _has_conflict(items, world: World) -> bool:
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i][1].chosen, items[j][1].chosen
            if a.person != b.person or a.day != b.day:
                continue
            ra, rb = _route(items[i][0], a.route_id), _route(items[j][0], b.route_id)
            if ra.window.overlaps(rb.window):
                return True
    return False


def _result(resp: Responsibility, occs: list[OccurrenceResult]) -> ResponsibilityResult:
    if not occs:
        return ResponsibilityResult(resp.id, resp.label, resp.weight, State.NOT_DUE, Tri.T, [], None, [], {}, [])
    feasibility = worst(o.value for o in occs)
    first_problem = next((o.date for o in occs if not o.prepared), None)
    performers: list[str] = []
    missing: dict[str, list[str]] = {}
    for o in occs:
        if o.chosen is not None:
            if o.chosen.person not in performers:
                performers.append(o.chosen.person)
            if o.chosen.policy_missing:
                bucket = missing.setdefault(o.chosen.person, [])
                for item in o.chosen.policy_missing:
                    if item not in bucket:
                        bucket.append(item)
    if feasibility is Tri.F:
        state = State.BLOCKED
    elif feasibility is Tri.U:
        state = State.NEEDS_CONFIRMATION
    elif missing:
        state = State.NEEDS_HANDOVER
    else:
        state = State.PREPARED
    reasons: dict[tuple, Reason] = {}
    for o in occs:
        for r in o.reasons:
            reasons.setdefault(r.key(), r)
    return ResponsibilityResult(
        resp.id, resp.label, resp.weight, state, feasibility, occs, first_problem, performers, missing, list(reasons.values())
    )


def summarise(results: dict[str, ResponsibilityResult]) -> Summary:
    total = len(results)
    counts = {s: 0 for s in State}
    weight_total = 0
    weight_ready = 0
    occ_weighted = 0.0
    for r in results.values():
        counts[r.state] += 1
        weight_total += r.weight
        if r.state.ready:
            weight_ready += r.weight
        occ_weighted += r.weight * r.coverage
    return Summary(
        total=total,
        ready=counts[State.PREPARED] + counts[State.NOT_DUE],
        prepared=counts[State.PREPARED],
        not_due=counts[State.NOT_DUE],
        needs_handover=counts[State.NEEDS_HANDOVER],
        needs_confirmation=counts[State.NEEDS_CONFIRMATION],
        blocked=counts[State.BLOCKED],
        weight_total=weight_total,
        weight_ready=weight_ready,
        occurrence_coverage=(occ_weighted / weight_total) if weight_total else 0.0,
    )


def _holder_message(res: Resource, holder: str, via: Resource | None, *, away: bool) -> str:
    """Say what is actually missing: the contact on the phone, the book in the drawer."""
    tail = f", and {holder} is away." if away else "."
    if via is not None and res.kind is ResourceKind.HANDSET:
        return f"{cap(via.label)} is only on {res.label}{tail}"
    if via is not None and res.kind is ResourceKind.LOCATION:
        return f"Only {holder} knows where {via.label} is kept ({res.label}){tail}"
    if via is not None and res.kind in (ResourceKind.ACCOUNT, ResourceKind.SERVICE):
        return f"{cap(via.label)} is only in {res.label}{tail}"
    if away:
        return f"Only {holder} has {res.label}, and {holder} is away."
    return f"{cap(res.label)} is with {holder} and hasn't been shared."


def resource_label(world: World, rid: str) -> str:
    res: Resource | None = world.resources.get(rid)
    return res.label if res else rid
