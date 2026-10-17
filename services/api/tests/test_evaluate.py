from datetime import date

from app.engine.evaluate import State, evaluate
from app.engine.model import (
    Assumption,
    HandoverRecord,
    Policy,
    Practical,
    ResourceKind,
    Understanding,
)
from app.engine.tri import Tri

from .helpers import access, busy, fact, once, people, res, resp, route, scenario, valid, weekly, win, world

DAY = date(2026, 11, 5)  # a Thursday inside the absence


def _one(w, s, rid):
    return evaluate(w, s).results[rid]


def test_holder_away_blocks_and_sharing_fixes():
    w = world(*people())
    w.resources["folder"] = res("folder", ResourceKind.LOCATION, holder="amma", label="the blue folder")
    w.responsibilities["r"] = resp("r", route("rt", "r", access("folder")), owners=["appa"])
    r = _one(w, scenario(), "r")
    assert r.state is State.BLOCKED
    assert r.reasons[0].code == "HOLDER_AWAY"
    w.resources["folder"].shared_with.add("appa")
    assert _one(w, scenario(), "r").state is State.PREPARED


def test_holder_present_but_not_shared_is_unknown():
    w = world(*people())
    w.resources["key"] = res("key", ResourceKind.ITEM, holder="aunty")
    w.responsibilities["r"] = resp("r", route("rt", "r", access("key")), owners=["appa"])
    r = _one(w, scenario(), "r")
    assert r.state is State.NEEDS_CONFIRMATION
    assert any(x.code == "NEEDS_HOLDER" for x in r.reasons)


def test_contact_on_any_phone_is_enough():
    w = world(*people())
    w.resources["phone_a"] = res("phone_a", ResourceKind.HANDSET, holder="amma")
    w.resources["phone_b"] = res("phone_b", ResourceKind.HANDSET, holder="appa")
    w.resources["contact"] = res("contact", ResourceKind.CONTACT, stored_on=["phone_a"], label="the driver's number")
    w.responsibilities["r"] = resp("r", route("rt", "r", access("contact")), owners=["appa"])
    r = _one(w, scenario(), "r")
    assert r.state is State.BLOCKED
    assert r.reasons[0].message == "The driver's number is only on phone_a, and Amma is away."
    w.resources["contact"].stored_on.append("phone_b")
    assert _one(w, scenario(), "r").state is State.PREPARED


def test_prerequisite_unavailable_in_scenario():
    w = world(*people())
    w.resources["number"] = res("number", ResourceKind.PHONE_NUMBER, holder="amma", shared_with={"appa"})
    w.resources["app"] = res("app", ResourceKind.ACCOUNT, holder="appa", requires=["number"])
    w.responsibilities["r"] = resp("r", route("rt", "r", access("app")), owners=["appa"])
    s = scenario(assumptions=[Assumption("a1", "resource_unavailable", "number", "the number stops")])
    r = _one(w, s, "r")
    assert r.state is State.BLOCKED
    assert r.reasons[0].code == "SCENARIO_UNAVAILABLE"
    assert _one(w, scenario(), "r").state is State.PREPARED


def test_generic_resource_is_available_to_everyone():
    w = world(*people())
    w.resources["counter"] = res("counter", ResourceKind.LOCATION, generic=True, holder="amma")
    w.responsibilities["r"] = resp("r", route("rt", "r", access("counter")), owners=["appa"])
    assert _one(w, scenario(), "r").state is State.PREPARED


def test_alternative_routes_are_never_mixed():
    # route 1 needs A (missing), route 2 needs B (missing): having A's partner in
    # route 2 must not satisfy route 1
    w = world(*people())
    w.resources["a"] = res("a", holder="amma")
    w.resources["b"] = res("b", holder="amma")
    w.resources["c"] = res("c", generic=True)
    w.responsibilities["r"] = resp("r", route("r1", "r", access("a"), access("c")), route("r2", "r", access("b")), owners=["appa"])
    assert _one(w, scenario(), "r").state is State.BLOCKED
    w.resources["b"].shared_with.add("appa")
    assert _one(w, scenario(), "r").state is State.PREPARED


def test_validity_and_renewal_projection():
    w = world(*people())
    w.resources["permit"] = res("permit", ResourceKind.PERMIT, valid_until=date(2026, 11, 20), renewed_by="renew", label="the permit")
    w.responsibilities["drive"] = resp("drive", route("rt", "drive", valid("permit")), owners=["appa"])
    renew_route = route("rr", "renew")
    w.responsibilities["renew"] = resp("renew", renew_route, recurrence=once(date(2026, 11, 20)), owners=["amma"])
    r = evaluate(w, scenario())
    assert r.results["drive"].state is State.BLOCKED
    assert r.results["drive"].first_problem == date(2026, 11, 21)
    assert any(x.code == "EXPIRES_NOT_RENEWABLE" for x in r.results["drive"].reasons)
    # a willing stand-in who hasn't finished the handover: the projection is unknown
    w.willingness[("appa", "renew")] = Tri.T
    r = evaluate(w, scenario())
    assert r.results["renew"].state is State.NEEDS_HANDOVER
    assert r.results["drive"].state is State.NEEDS_CONFIRMATION
    assert any(x.code == "RENEWAL_NOT_READY" for x in r.results["drive"].reasons)
    # once the handover is complete, the renewal is prepared and the permit stays valid
    w.handovers[("appa", "renew")] = HandoverRecord("appa", "renew", understanding=Understanding.VIEWED)
    r = evaluate(w, scenario())
    assert r.results["renew"].state is State.PREPARED
    assert r.results["drive"].state is State.PREPARED
    # no renewal recorded at all: expired
    w2 = world(*people())
    w2.resources["permit"] = res("permit", ResourceKind.PERMIT, valid_until=date(2026, 11, 20))
    w2.responsibilities["drive"] = resp("drive", route("rt", "drive", valid("permit")), owners=["appa"])
    assert any(x.code == "EXPIRED" for x in _one(w2, scenario(), "drive").reasons)


def test_expiry_before_the_absence():
    w = world(*people())
    w.resources["permit"] = res("permit", ResourceKind.PERMIT, valid_until=date(2026, 10, 20), renewed_by="renew")
    w.responsibilities["drive"] = resp("drive", route("rt", "drive", valid("permit")), owners=["appa"])
    w.responsibilities["renew"] = resp("renew", route("rr", "renew"), recurrence=once(date(2026, 10, 20)), owners=["amma"])
    r = evaluate(w, scenario())
    assert r.results["renew"].state is State.NOT_DUE
    assert r.results["drive"].reasons[0].code == "EXPIRES_BEFORE_ABSENCE"


def test_performers():
    w = world(*people())
    w.responsibilities["r"] = resp("r", route("rt", "r", performers=["kid"]))
    assert _one(w, scenario(), "r").reasons[0].code == "MINOR"
    w.responsibilities["r"] = resp("r", route("rt", "r"), owners=["amma"])
    w.willingness[("appa", "r")] = Tri.F
    r = _one(w, scenario(), "r")
    assert r.state is State.BLOCKED
    assert {x.code for x in r.reasons} >= {"PERFORMER_AWAY", "NOT_WILLING"}
    w.willingness[("appa", "r")] = Tri.U
    r = _one(w, scenario(), "r")
    assert r.state is State.NEEDS_CONFIRMATION
    assert any(x.code == "WILLINGNESS_UNKNOWN" for x in r.reasons)


def test_busy_window_and_flexible_days():
    w = world(*people())
    w.commitments.append(busy("c1", "appa", weekly(3), "03:30", "10:00", "airport runs"))
    rt = route("rt", "r", window=win("07:00", "09:00"))
    w.responsibilities["r"] = resp("r", rt, recurrence=once(DAY), owners=["appa"])
    r = _one(w, scenario(), "r")
    assert r.state is State.BLOCKED
    assert r.reasons[0].code == "BUSY"
    rt.flexible_days = 1  # may be done the day before
    r = _one(w, scenario(), "r")
    assert r.state is State.PREPARED
    assert r.occurrences[0].chosen.day == date(2026, 11, 4)


def test_commitment_exception_frees_the_day():
    w = world(*people())
    w.commitments.append(busy("c1", "appa", weekly(3), "03:30", "10:00"))
    w.responsibilities["r"] = resp("r", route("rt", "r", window=win("07:00", "09:00")), recurrence=once(DAY), owners=["appa"])
    w.commitment_exceptions.add(("c1", DAY))
    assert _one(w, scenario(), "r").state is State.PREPARED


def test_weekday_restriction():
    w = world(*people())
    w.responsibilities["r"] = resp("r", route("rt", "r", weekdays=(0, 1, 2, 3, 4)), recurrence=once(date(2026, 11, 8)), owners=["appa"])
    assert _one(w, scenario(), "r").reasons[0].code == "WEEKDAY_CLOSED"


def test_facts():
    w = world(*people())
    w.facts["ok"] = Tri.F
    w.fact_labels["ok"] = "the school has a second number"
    w.responsibilities["r"] = resp("r", route("rt", "r", fact("ok")), owners=["appa"])
    assert _one(w, scenario(), "r").reasons[0].message == "Not true yet: the school has a second number."
    w.facts["ok"] = Tri.U
    assert _one(w, scenario(), "r").state is State.NEEDS_CONFIRMATION
    w.facts["ok"] = Tri.T
    assert _one(w, scenario(), "r").state is State.PREPARED


def test_evidence_policy_levels():
    w = world(*people())
    w.willingness[("appa", "r")] = Tri.T
    r = resp("r", route("rt", "r"), owners=["amma"], policy=Policy.LIGHT)
    w.responsibilities["r"] = r
    res_ = _one(w, scenario(), "r")
    assert res_.state is State.NEEDS_HANDOVER and res_.missing == {"appa": ["VIEW"]}
    w.handovers[("appa", "r")] = HandoverRecord("appa", "r", understanding=Understanding.VIEWED)
    assert _one(w, scenario(), "r").state is State.PREPARED

    r.policy = Policy.STANDARD
    assert _one(w, scenario(), "r").missing == {"appa": ["EXPLAIN"]}
    w.handovers[("appa", "r")].understanding = Understanding.PRACTICED_WITH_HELP  # a hint was needed
    assert _one(w, scenario(), "r").missing == {"appa": ["EXPLAIN"]}
    w.handovers[("appa", "r")].understanding = Understanding.UNASSISTED
    assert _one(w, scenario(), "r").state is State.PREPARED

    r.policy = Policy.CRITICAL
    r.demo_step = "show the key step"
    assert _one(w, scenario(), "r").missing == {"appa": ["SHOW"]}
    w.handovers[("appa", "r")].practical = Practical.SELF_REPORTED  # saying it isn't showing it
    assert _one(w, scenario(), "r").missing == {"appa": ["SHOW"]}
    w.handovers[("appa", "r")].practical = Practical.WITNESSED
    assert _one(w, scenario(), "r").state is State.PREPARED


def test_knowing_when_is_separate_from_doing():
    w = world(*people())
    w.willingness[("appa", "r")] = Tri.T
    w.resources["sms"] = res("sms", ResourceKind.SERVICE, holder="amma")
    r = resp(
        "r",
        route("rt", "r"),
        owners=["amma"],
        recurrence=once(DAY),
        policy=Policy.LIGHT,
        awareness_required=True,
        awareness_sources=["sms"],
    )
    w.responsibilities["r"] = r
    w.handovers[("appa", "r")] = HandoverRecord("appa", "r", understanding=Understanding.VIEWED)
    assert _one(w, scenario(), "r").missing == {"appa": ["KNOWS_WHEN"]}
    w.card_entries.add("r")
    assert _one(w, scenario(), "r").state is State.PREPARED


def test_no_route_and_not_due():
    w = world(*people())
    w.responsibilities["r"] = resp("r", recurrence=once(DAY))
    r = _one(w, scenario(), "r")
    assert r.state is State.NEEDS_CONFIRMATION and r.reasons[0].code == "NO_ROUTE"
    w.responsibilities["r"] = resp("r", route("rt", "r"), recurrence=once(date(2027, 3, 1)), owners=["appa"])
    assert _one(w, scenario(), "r").state is State.NOT_DUE


def test_summary_counts_and_weights():
    w = world(*people())
    w.responsibilities["a"] = resp("a", route("ra", "a"), owners=["appa"], weight=3)
    w.responsibilities["b"] = resp("b", route("rb", "b"), owners=["amma"], weight=2)
    w.responsibilities["c"] = resp("c", route("rc", "c"), owners=["appa"], recurrence=once(date(2027, 5, 1)), weight=1)
    s = evaluate(w, scenario()).summary
    assert (s.total, s.ready, s.prepared, s.not_due, s.blocked) == (3, 2, 1, 1, 1)
    assert (s.weight_ready, s.weight_total, s.ready_pct) == (4, 6, 66.7)
