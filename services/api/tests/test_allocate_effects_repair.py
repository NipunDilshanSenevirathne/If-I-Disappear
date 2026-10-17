from datetime import date

from app.engine import effects as fx
from app.engine.effects import Effect, apply_effects
from app.engine.evaluate import State, evaluate
from app.engine.model import Assumption, Policy, ResourceKind
from app.engine.repair import plan
from app.engine.tri import Tri

from .helpers import access, busy, once, people, res, resp, route, scenario, weekly, win, world

DAY = date(2026, 11, 5)


# ---------------------------------------------------------------- allocation


def test_one_person_cannot_be_in_two_places():
    w = world(*people())
    w.responsibilities["clinic"] = resp(
        "clinic", route("rc", "clinic", window=win("07:00", "11:00")), recurrence=once(DAY), owners=["appa"], weight=3
    )
    w.responsibilities["van"] = resp(
        "van", route("rv", "van", window=win("08:00", "08:30")), recurrence=once(DAY), owners=["appa"], weight=1
    )
    r = evaluate(w, scenario())
    assert r.results["clinic"].state is State.PREPARED
    assert r.results["van"].state is State.BLOCKED
    assert r.results["van"].reasons[0].code == "CAPACITY_CONFLICT"


def test_a_second_person_resolves_the_clash():
    w = world(*people())
    w.responsibilities["clinic"] = resp(
        "clinic", route("rc", "clinic", window=win("07:00", "11:00")), recurrence=once(DAY), owners=["appa"], weight=3
    )
    w.responsibilities["van"] = resp(
        "van", route("rv", "van", window=win("08:00", "08:30")), recurrence=once(DAY), owners=["appa"], weight=1
    )
    w.willingness[("aunty", "van")] = Tri.T
    r = evaluate(w, scenario())
    assert r.results["clinic"].state is State.PREPARED
    assert r.results["van"].occurrences[0].chosen.person == "aunty"


# ---------------------------------------------------------------- effects


def test_effects_change_a_copy_only():
    w = world(*people())
    w.resources["c"] = res("c", ResourceKind.CONTACT)
    w.resources["loc"] = res("loc", ResourceKind.LOCATION, holder="amma")
    w.resources["permit"] = res("permit", ResourceKind.PERMIT, valid_until=date(2026, 11, 20))
    s = scenario(assumptions=[Assumption("a1", "resource_unavailable", "c", "stops", negotiable=True)])
    applied = apply_effects(
        w,
        s,
        [
            Effect(fx.WILLING, person="appa", responsibility="r"),
            Effect(fx.SHARE, resource="loc", person="appa"),
            Effect(fx.STORE_ON, resource="c", container="phone"),
            Effect(fx.FACT_TRUE, fact="f"),
            Effect(fx.UNDERSTANDING, person="appa", responsibility="r", level=3),
            Effect(fx.PRACTICAL, person="appa", responsibility="r", level=2),
            Effect(fx.CARD, responsibility="r"),
            Effect(fx.VALID_UNTIL, resource="permit", new_date=date(2027, 11, 20)),
            Effect(fx.DROP_ASSUMPTION, assumption="a1"),
            Effect(fx.COMMITMENT_OFF, commitment="c1", day=DAY),
        ],
    )
    w2, s2 = applied.world, applied.scenario
    assert w2.willingness[("appa", "r")] is Tri.T and ("appa", "r") not in w.willingness
    assert "appa" in w2.resources["loc"].shared_with and not w.resources["loc"].shared_with
    assert w2.resources["c"].stored_on == ["phone"]
    assert w2.facts["f"] is Tri.T
    assert int(w2.handovers[("appa", "r")].understanding) == 3 and int(w2.handovers[("appa", "r")].practical) == 2
    assert "r" in w2.card_entries
    assert w2.resources["permit"].valid_until == date(2027, 11, 20)
    assert s2.assumptions == [] and len(s.assumptions) == 1
    assert ("c1", DAY) in w2.commitment_exceptions
    assert applied.notes == []


# ---------------------------------------------------------------- repair


def _handover_world():
    w = world(*people())
    w.resources["phone_amma"] = res("phone_amma", ResourceKind.HANDSET, holder="amma", label="Amma's phone")
    w.resources["phone_appa"] = res("phone_appa", ResourceKind.HANDSET, holder="appa", label="Appa's phone")
    w.resources["driver"] = res("driver", ResourceKind.CONTACT, stored_on=["phone_amma"], label="the driver's number")
    w.responsibilities["van"] = resp(
        "van",
        route("rv", "van", access("driver")),
        recurrence=once(DAY),
        owners=["amma"],
        weight=2,
        policy=Policy.STANDARD,
    )
    return w


def test_plan_bundles_every_step_a_handover_needs():
    w = _handover_world()
    p = plan(w, scenario(), budget_minutes=60)
    assert p.exhaustive
    assert p.before.ready == 0 and p.after.ready == 1
    kinds = [s.kind for s in p.steps]
    assert kinds == ["ASK", "SHARE_CONTACT", "PRACTICE"]
    # planned effects are hypothetical: the world itself didn't change
    assert evaluate(w, scenario()).results["van"].state is State.BLOCKED


def test_budget_limits_the_plan():
    w = _handover_world()
    p = plan(w, scenario(), budget_minutes=5)
    assert p.bundles == [] and p.after.ready == 0


def test_swaps_of_one_commitment_become_one_conversation():
    w = world(*people())
    w.commitments.append(busy("c1", "appa", weekly(3), "03:30", "10:00", "airport runs"))
    w.willingness[("appa", "clinic")] = Tri.T
    w.responsibilities["clinic"] = resp(
        "clinic",
        route("rc", "clinic", window=win("07:00", "11:00")),
        recurrence=weekly(3, anchor=date(2026, 11, 5)),
        owners=["amma"],
        weight=3,
    )
    p = plan(w, scenario(), budget_minutes=60)
    swaps = [s for s in p.steps if s.kind == "ASK_SWAP"]
    assert len(swaps) == 1
    assert len(swaps[0].dates) == 4  # Thursdays 5, 12, 19, 26 Nov
    assert swaps[0].title.startswith("Ask Appa: can you be free from airport runs on 4 Thursdays")
    assert p.after.prepared == 1


def test_a_booked_commitment_is_never_moved():
    w = world(*people())
    w.commitments.append(busy("c1", "appa", once(DAY), "04:00", "21:00", "a booked trip", movable=False))
    w.willingness[("appa", "clinic")] = Tri.T
    w.responsibilities["clinic"] = resp(
        "clinic", route("rc", "clinic", window=win("07:00", "11:00")), recurrence=once(DAY), owners=["amma"], weight=3
    )
    p = plan(w, scenario(), budget_minutes=120)
    assert p.bundles == []
    assert p.after.blocked == 1


def test_renewing_early_is_offered_as_an_alternative():
    w = world(*people())
    w.resources["permit"] = res("permit", ResourceKind.PERMIT, valid_until=date(2026, 11, 20), renewed_by="renew", label="the permit")
    w.responsibilities["renew"] = resp(
        "renew", route("rr", "renew"), recurrence=once(date(2026, 11, 20)), owners=["amma"], weight=3, policy=Policy.STANDARD
    )
    p = plan(w, scenario(), budget_minutes=120)
    ids = {b.id for b in p.candidates}
    assert "renew-early:renew" in ids
    assert p.after.ready == 1
