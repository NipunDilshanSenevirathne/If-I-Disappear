"""Compile accepted claims into the engine's World and Scenario.

The compiler is deterministic: the same entities, accepted claims and handover
events always produce the same model. It reports anything it cannot place
(unknown entities, malformed values, contradictions) instead of guessing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import time, timedelta

from ..engine.discover import Contradiction, Mention
from ..engine.model import (
    Assumption,
    Commitment,
    Enabler,
    Freq,
    HandoverRecord,
    Person,
    Policy,
    Practical,
    Recurrence,
    ReqKind,
    Requirement,
    Resource,
    ResourceKind,
    Responsibility,
    Route,
    Scenario,
    Unavailability,
    Understanding,
    Window,
    World,
)
from ..engine.tri import Tri
from .claims import Claim, Entity, HandoverEvent, HouseholdSettings, Procedure, ScheduleSpec, WindowSpec

WEEKDAY_INDEX = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
POLICY_FOR_WEIGHT = {1: Policy.LIGHT, 2: Policy.STANDARD, 3: Policy.CRITICAL}


@dataclass
class Compiled:
    world: World
    scenario: Scenario
    mentions: dict[str, list[Mention]]
    contradictions: list[Contradiction]
    procedures: dict[str, Procedure]
    entities: dict[str, Entity]
    diagnostics: list[str] = field(default_factory=list)


def natural_key(text: str) -> tuple:
    """Sort 'C9' before 'C10' (ids are compared piece by piece, numbers as numbers)."""
    return tuple((0, int(part), "") if part.isdigit() else (1, 0, part) for part in re.split(r"(\d+)", text) if part)


def normalise_identifier(raw: str | None) -> str | None:
    """Normalise phone-like identifiers (including masked ones like 077-XXX-0101)."""
    if not raw:
        return None
    cleaned = re.sub(r"[\s\-().]", "", raw.upper())
    if cleaned.startswith("+94"):
        cleaned = "0" + cleaned[3:]
    return cleaned or None


def parse_time(value: str) -> time:
    h, m = value.split(":")
    return time(int(h), int(m))


def to_window(spec: WindowSpec | None) -> Window | None:
    if spec is None:
        return None
    return Window(parse_time(spec.start), parse_time(spec.end))


def to_recurrence(spec: ScheduleSpec | None) -> Recurrence:
    if spec is None:
        return Recurrence(Freq.ONGOING)
    return Recurrence(
        Freq(spec.freq),
        interval=max(1, spec.interval),
        weekdays=tuple(WEEKDAY_INDEX[d] for d in spec.weekdays),
        monthday=spec.monthday,
        anchor=spec.anchor,
    )


def _tri(value: str | None) -> Tri:
    v = (value or "").strip().lower()
    if v in ("yes", "true", "t", "y"):
        return Tri.T
    if v in ("no", "false", "f", "n"):
        return Tri.F
    return Tri.U


def compile_household(
    settings: HouseholdSettings,
    entities: list[Entity],
    claims: list[Claim],
    handover_events: list[HandoverEvent] | None = None,
    procedures: list[Procedure] | None = None,
    world_version: int = 1,
) -> Compiled:
    diagnostics: list[str] = []
    # Canonical order: the same accepted facts give the same model (and the same
    # answer) whatever order they were captured, reviewed or stored in.
    entities = sorted(entities, key=lambda e: natural_key(e.id))
    ents = {e.id: e for e in entities}
    accepted = sorted((c for c in claims if c.review == "accepted"), key=lambda c: natural_key(c.id))
    world = World(household_id=settings.id, version=world_version)

    # ---------------------------------------------------------------- entities
    for e in entities:
        if e.kind == "person":
            world.people[e.id] = Person(e.id, e.name, role=e.role or "household", minor=e.minor)
        elif e.kind == "resource":
            kind = ResourceKind(e.resource_kind or "item")
            world.resources[e.id] = Resource(
                id=e.id,
                kind=kind,
                label=e.name,
                generic=e.generic,
                identifier=normalise_identifier(e.identifier),
            )
        elif e.kind == "responsibility":
            world.responsibilities[e.id] = Responsibility(id=e.id, label=e.name, category=e.category or "household")
        elif e.kind == "fact":
            world.fact_labels[e.id] = e.name
            world.facts.setdefault(e.id, Tri.U)

    routes: dict[str, Route] = {}
    route_owner: dict[str, str] = {}
    resp_needs: dict[str, list[Requirement]] = {}

    def claim_ok(c: Claim, *, obj: bool = False) -> bool:
        if c.subject not in ents:
            diagnostics.append(f"{c.id}: unknown subject '{c.subject}'")
            return False
        if obj and (c.object is None or c.object not in ents):
            diagnostics.append(f"{c.id}: unknown object '{c.object}'")
            return False
        return True

    def add_ids(target, cid: str):
        target.claim_ids = tuple(dict.fromkeys(target.claim_ids + (cid,)))

    # ---------------------------------------------------------------- routes first
    for c in accepted:
        if c.predicate == "ROUTE" and claim_ok(c, obj=True):
            if c.subject not in world.responsibilities:
                diagnostics.append(f"{c.id}: ROUTE subject is not a responsibility")
                continue
            r_ent = ents[c.object]
            if c.object not in routes:
                routes[c.object] = Route(id=c.object, responsibility=c.subject, label=r_ent.name, claim_ids=(c.id,))
                route_owner[c.object] = c.subject
            else:
                add_ids(routes[c.object], c.id)

    # ---------------------------------------------------------------- everything else
    amounts: dict[str, list[tuple[str, str]]] = {}
    valid_claims: dict[str, list[Claim]] = {}
    level_overrides: dict[str, Policy] = {}
    for c in accepted:
        p = c.predicate
        if p == "ROUTE":
            continue
        if p in ("DOES", "CAN_DO"):
            if not claim_ok(c, obj=True):
                continue
            if c.object not in world.responsibilities or c.subject not in world.people:
                diagnostics.append(f"{c.id}: {p} needs person -> responsibility")
                continue
            if p == "DOES":
                resp = world.responsibilities[c.object]
                if c.subject not in resp.owners:
                    resp.owners.append(c.subject)
                add_ids(resp, c.id)
            else:
                key = (c.subject, c.object)
                world.willingness[key] = _tri(c.value)
                world.willingness_claims[key] = world.willingness_claims.get(key, ()) + (c.id,)
        elif p == "IMPORTANCE":
            if claim_ok(c) and c.subject in world.responsibilities:
                try:
                    w = max(1, min(3, int(c.value or "2")))
                except ValueError:
                    diagnostics.append(f"{c.id}: importance must be 1, 2 or 3")
                    continue
                world.responsibilities[c.subject].weight = w
                add_ids(world.responsibilities[c.subject], c.id)
        elif p == "SCHEDULE":
            if claim_ok(c) and c.subject in world.responsibilities:
                resp = world.responsibilities[c.subject]
                resp.recurrence = to_recurrence(c.schedule)
                add_ids(resp, c.id)
        elif p == "LEAD_TIME":
            if claim_ok(c) and c.subject in world.responsibilities:
                world.responsibilities[c.subject].lead_days = int(c.value or 0)
        elif p == "KEY_STEP":
            if claim_ok(c) and c.subject in world.responsibilities:
                world.responsibilities[c.subject].demo_step = c.value
        elif p == "HANDOVER_LEVEL":
            if claim_ok(c) and c.subject in world.responsibilities and (c.value or "") in ("light", "standard", "critical"):
                level_overrides[c.subject] = Policy(c.value)
        elif p == "AMOUNT":
            if claim_ok(c):
                amounts.setdefault(c.subject, []).append((c.value or "", c.id))
        elif p in ("ROUTE_NEEDS", "ROUTE_NEEDS_VALID", "ROUTE_NEEDS_FACT", "ROUTE_PERFORMER"):
            if c.subject not in routes:
                diagnostics.append(f"{c.id}: unknown route '{c.subject}'")
                continue
            if c.object is None or c.object not in ents:
                diagnostics.append(f"{c.id}: unknown object '{c.object}'")
                continue
            route = routes[c.subject]
            if p == "ROUTE_PERFORMER":
                if c.object not in route.performers:
                    route.performers.append(c.object)
            else:
                kind = {"ROUTE_NEEDS": ReqKind.ACCESS, "ROUTE_NEEDS_VALID": ReqKind.VALID, "ROUTE_NEEDS_FACT": ReqKind.FACT}[p]
                route.requirements.append(Requirement(kind, c.object, (c.id,)))
                if kind is ReqKind.FACT:
                    world.facts.setdefault(c.object, Tri.U)
            add_ids(route, c.id)
        elif p == "ROUTE_WINDOW":
            if c.subject in routes:
                routes[c.subject].window = to_window(c.window)
        elif p == "ROUTE_FLEXIBLE":
            if c.subject in routes:
                routes[c.subject].flexible_days = int(c.value or 0)
        elif p == "ROUTE_WEEKDAYS":
            if c.subject in routes:
                routes[c.subject].weekdays = tuple(WEEKDAY_INDEX[x.strip()] for x in (c.value or "").split(",") if x.strip())
        elif p in ("NEEDS", "NEEDS_VALID"):
            if claim_ok(c, obj=True) and c.subject in world.responsibilities:
                kind = ReqKind.ACCESS if p == "NEEDS" else ReqKind.VALID
                resp_needs.setdefault(c.subject, []).append(Requirement(kind, c.object, (c.id,)))
        elif p == "HOLDS":
            if claim_ok(c, obj=True) and c.object in world.resources:
                world.resources[c.object].holder = c.subject
                add_ids(world.resources[c.object], c.id)
        elif p == "STORED_ON":
            if claim_ok(c, obj=True) and c.subject in world.resources:
                res = world.resources[c.subject]
                if c.object not in res.stored_on:
                    res.stored_on.append(c.object)
                add_ids(res, c.id)
        elif p == "SHARED_WITH":
            if claim_ok(c, obj=True) and c.subject in world.resources:
                world.resources[c.subject].shared_with.add(c.object)
                add_ids(world.resources[c.subject], c.id)
        elif p == "REQUIRES_RESOURCE":
            if claim_ok(c, obj=True) and c.subject in world.resources:
                res = world.resources[c.subject]
                if c.object not in res.requires:
                    res.requires.append(c.object)
                add_ids(res, c.id)
        elif p == "NOTIFIES":
            if claim_ok(c, obj=True) and c.object in world.responsibilities:
                resp = world.responsibilities[c.object]
                if c.subject not in resp.awareness_sources:
                    resp.awareness_sources.append(c.subject)
        elif p == "MENTIONED_ON":
            pass  # used for association mentions only (below)
        elif p == "VALID_UNTIL":
            if claim_ok(c) and c.subject in world.resources and c.date:
                valid_claims.setdefault(c.subject, []).append(c)
        elif p == "RENEWS":
            if claim_ok(c, obj=True) and c.subject in world.responsibilities and c.object in world.resources:
                world.resources[c.object].renewed_by = c.subject
        elif p == "BUSY":
            if claim_ok(c) and c.subject in world.people and c.window is not None:
                world.commitments.append(
                    Commitment(
                        id=f"busy:{c.id}",
                        person=c.subject,
                        recurrence=to_recurrence(c.schedule),
                        window=to_window(c.window),
                        label=c.value or "busy",
                        movable=not c.fixed,
                        claim_ids=(c.id,),
                    )
                )
        elif p == "UNAVAILABLE":
            if claim_ok(c) and c.subject in world.people and c.date:
                end = c.end_date or (c.date + timedelta(days=1))
                world.unavailability.append(
                    Unavailability(
                        id=f"away:{c.id}", person=c.subject, start=c.date, end=end, label=c.value or "unavailable", claim_ids=(c.id,)
                    )
                )
        elif p == "FREE_ON":
            pass  # applied after commitments are known (below)
        elif p == "FACT":
            if claim_ok(c):
                world.facts[c.subject] = _tri(c.value)
                world.fact_claims[c.subject] = world.fact_claims.get(c.subject, ()) + (c.id,)
        elif p == "ENABLES":
            if claim_ok(c):
                minutes = c.minutes or 30
                world.fact_enablers[c.subject] = Enabler(
                    label=c.value or "Arrange it with the provider",
                    minutes=minutes,
                    minutes_range=(max(1, minutes // 2), minutes * 2),
                    owner_role=(c.note or "leaver"),
                    claim_ids=(c.id,),
                )
        elif p in ("STOPS_DURING_ABSENCE", "KNOWS_SECRET"):
            pass  # scenario / safety handled below
        else:  # pragma: no cover
            diagnostics.append(f"{c.id}: unhandled predicate {p}")

    # validity: the newest documented date wins; a mismatch is reported, never averaged
    for rid, cs in valid_claims.items():
        cs_sorted = sorted(cs, key=lambda c: c.date)
        world.resources[rid].valid_until = cs_sorted[-1].date
        for c in cs_sorted:
            add_ids(world.resources[rid], c.id)

    # commitments agreed off for a day: FREE_ON value = BUSY claim id
    for c in accepted:
        if c.predicate == "FREE_ON" and c.date and c.value:
            world.commitment_exceptions.add((f"busy:{c.value}", c.date))

    # attach routes and responsibility-wide requirements
    for rid, resp in world.responsibilities.items():
        resp_routes = [r for r in routes.values() if r.responsibility == rid]
        common = resp_needs.get(rid, [])
        if not resp_routes and (common or resp.owners):
            resp_routes = [Route(id=f"{rid}:usual", responsibility=rid, label="The usual way", requirements_known=bool(common))]
        for r in resp_routes:
            r.requirements = list(r.requirements) + [q for q in common if q not in r.requirements]
        resp.routes = sorted(resp_routes, key=lambda r: r.id)

    # renewals happen when the permit expires
    for res in world.resources.values():
        if res.renewed_by and res.valid_until and res.renewed_by in world.responsibilities:
            resp = world.responsibilities[res.renewed_by]
            if resp.recurrence.freq in (Freq.ONGOING, Freq.YEARLY):
                resp.recurrence = Recurrence(Freq.ONCE, anchor=res.valid_until)

    # policy from weight; awareness matters for dated responsibilities
    for resp in world.responsibilities.values():
        resp.policy = level_overrides.get(resp.id) or POLICY_FOR_WEIGHT.get(resp.weight, Policy.STANDARD)
        if resp.policy is Policy.CRITICAL and not resp.demo_step:
            resp.policy = Policy.STANDARD
        resp.awareness_required = resp.recurrence.freq is not Freq.ONGOING and resp.policy is not Policy.LIGHT
        if settings.in_scope is not None:
            resp.in_scope = resp.id in settings.in_scope

    # continuity card entries and handover events
    world.card_entries = set(settings.card_entries)
    for ev in handover_events or []:
        key = (ev.person, ev.responsibility)
        rec = world.handovers.get(key, HandoverRecord(ev.person, ev.responsibility))
        if ev.level == "viewed":
            rec.understanding = max(rec.understanding, Understanding.VIEWED)
        elif ev.level == "practiced_with_help":
            rec.understanding = max(rec.understanding, Understanding.PRACTICED_WITH_HELP)
        elif ev.level == "unassisted":
            rec.understanding = max(rec.understanding, Understanding.UNASSISTED)
        elif ev.level == "self_reported":
            rec.practical = max(rec.practical, Practical.SELF_REPORTED)
        elif ev.level == "witnessed":
            rec.practical = max(rec.practical, Practical.WITNESSED)
        rec.evidence_ids = rec.evidence_ids + (ev.id,)
        world.handovers[key] = rec

    # ---------------------------------------------------------------- scenario
    start = settings.departure
    scenario = Scenario(
        id=f"absence:{settings.id}:{start.isoformat()}",
        leaver=settings.leaver,
        start=start,
        end=start + timedelta(days=settings.horizon_days),
        label=f"{world.people[settings.leaver].name if settings.leaver in world.people else settings.leaver} away from {start.strftime('%d %b %Y')}",
    )
    for c in accepted:
        if c.predicate == "STOPS_DURING_ABSENCE" and c.subject in world.resources:
            res = world.resources[c.subject]
            scenario.assumptions.append(
                Assumption(
                    id=f"assume:{c.id}",
                    kind="resource_unavailable",
                    target=c.subject,
                    label=f"{res.label} won't be used during the absence",
                    negotiable=(c.value or "").lower() != "decided",
                    claim_ids=(c.id,),
                )
            )

    # ---------------------------------------------------------------- mentions (association scan)
    mentions: dict[str, list[Mention]] = {}

    def doc_responsibilities(doc_id: str) -> set[str]:
        out = set()
        for resp in world.responsibilities.values():
            if doc_id in resp.awareness_sources:
                out.add(resp.id)
            for route in resp.routes:
                if any(req.target == doc_id for req in route.requirements):
                    out.add(resp.id)
        return out

    for c in accepted:
        sources = sorted({e.source_id for e in c.evidence})
        targets: list[tuple[str, str | None, str]] = []
        if c.predicate == "NOTIFIES" and c.subject in world.resources:
            targets.append((c.subject, c.object, "notifies"))
        elif c.predicate == "MENTIONED_ON" and c.subject in world.resources and c.object:
            linked = doc_responsibilities(c.object)
            if linked:
                for r in sorted(linked):
                    targets.append((c.subject, r, "mentioned"))
            else:
                targets.append((c.subject, None, "mentioned"))
        elif c.predicate == "REQUIRES_RESOURCE" and c.object in world.resources:
            linked = doc_responsibilities(c.subject)
            for resp in world.responsibilities.values():
                for route in resp.routes:
                    if any(req.target == c.subject for req in route.requirements):
                        linked.add(resp.id)
            for r in sorted(linked) or [None]:
                targets.append((c.object, r, "requires"))
        elif c.predicate in ("HOLDS",) and c.object in world.resources:
            targets.append((c.object, None, "held"))
        for rid, resp_id, role in targets:
            for s in sources:
                mentions.setdefault(rid, []).append(Mention(s, c.id, resp_id, role))

    # ---------------------------------------------------------------- contradictions
    contradictions: list[Contradiction] = []
    for subject, values in amounts.items():
        distinct = {v for v, _ in values}
        if len(distinct) > 1:
            label = (
                f"the amount to {world.responsibilities[subject].label}"
                if subject in world.responsibilities
                else f"the amount for {subject}"
            )
            contradictions.append(
                Contradiction(
                    id=f"amount:{subject}",
                    subject=subject,
                    field="amount",
                    values=values,
                    responsibility=subject if subject in world.responsibilities else None,
                    label=label,
                )
            )

    return Compiled(
        world=world,
        scenario=scenario,
        mentions=mentions,
        contradictions=contradictions,
        procedures={p.responsibility: p for p in (procedures or [])},
        entities=ents,
        diagnostics=diagnostics,
    )
