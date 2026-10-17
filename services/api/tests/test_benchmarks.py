"""Every benchmark household against its hand-written gold file.

The households were written as stories first (sources, then claims quoting them,
then what the engine *should* conclude), and only then run through the engine.
"""

import json
import random

import pytest

from app.domain.household import demo_household
from app.engine.discover import discover
from app.engine.evaluate import evaluate
from app.engine.repair import plan
from app.engine.serialize import finding_dict, plan_dict, result_dict
from app.verify.gold import benchmark_households, check_household
from app.verify.quotes import check_claim

HOUSEHOLDS = benchmark_households()


def test_there_are_several_benchmark_households():
    assert len(HOUSEHOLDS) >= 4
    assert "perera" in HOUSEHOLDS


@pytest.mark.parametrize("hid", HOUSEHOLDS)
def test_every_claim_quotes_its_source_exactly(hid):
    h = demo_household(hid)
    sources = h.source_map()
    bad = [(c.id, r.issues) for c in h.claims if not (r := check_claim(c, sources)).supported]
    assert bad == []


@pytest.mark.parametrize("hid", HOUSEHOLDS)
def test_household_compiles_cleanly(hid):
    c = demo_household(hid).compile()
    assert c.diagnostics == []


@pytest.mark.parametrize("hid", HOUSEHOLDS)
def test_engine_matches_gold(hid):
    report = check_household(hid)
    failures = [c.describe() for c in report.checks if not c.ok]
    assert failures == []
    assert report.of("finding"), "gold has findings"


def _snapshot(h, budget):
    c = h.compile()
    result = evaluate(c.world, c.scenario)
    findings = discover(c.world, c.scenario, result, c.mentions, c.contradictions)
    p = plan(c.world, c.scenario, result, budget_minutes=budget)
    return json.dumps(
        {
            "result": result_dict(c.world, c.scenario, result),
            "findings": [finding_dict(c.world, f) for f in findings],
            "plan": plan_dict(c.world, c.scenario, p),
        },
        sort_keys=True,
        default=str,
    )


@pytest.mark.parametrize("hid", HOUSEHOLDS)
def test_claim_order_does_not_change_the_answer(hid):
    h = demo_household(hid)
    budget = h.settings.budget_minutes
    first = _snapshot(h, budget)
    shuffled = h.copy()
    random.Random(7).shuffle(shuffled.claims)
    shuffled.entities = list(reversed(shuffled.entities))
    assert _snapshot(shuffled, budget) == first
