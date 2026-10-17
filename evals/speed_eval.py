"""Section 6: same facts, same answer; and how long the engine takes.

The engine's output (readiness, findings, plan) is hashed and compared across
repeated runs, across fresh Python processes with different hash seeds (which
changes the iteration order of sets), and with the household's claims and
entities shuffled. Timings are wall-clock on the machine that ran the report.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import statistics
import subprocess
import sys
import time

from app.domain.household import demo_household
from app.engine.discover import discover
from app.engine.evaluate import evaluate
from app.engine.repair import plan
from app.engine.serialize import finding_dict, plan_dict, result_dict
from app.verify.gold import benchmark_households

from .common import API, Metric, Section, ratio


def answer(h) -> dict:
    c = h.compile()
    r = evaluate(c.world, c.scenario)
    f = discover(c.world, c.scenario, r, c.mentions, c.contradictions)
    p = plan(c.world, c.scenario, r, budget_minutes=h.settings.budget_minutes)
    return {
        "result": result_dict(c.world, c.scenario, r),
        "findings": [finding_dict(c.world, x) for x in f],
        "plan": plan_dict(c.world, c.scenario, p),
    }


def digest(h) -> str:
    return hashlib.sha256(json.dumps(answer(h), sort_keys=True, default=str).encode()).hexdigest()


_CHILD = """
import sys, json
sys.path.insert(0, {api!r})
sys.path.insert(0, {root!r})
from evals.speed_eval import digest
from app.domain.household import demo_household
print(json.dumps({{h: digest(demo_household(h)) for h in {households!r}}}))
"""


def _child_digests(households: list[str], seed: str) -> dict[str, str] | None:
    env = dict(os.environ, PYTHONHASHSEED=seed, AI_MODE="fixture")
    code = _CHILD.format(api=str(API), root=str(API.parents[1]), households=households)
    try:
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=300, check=True)
        return json.loads(out.stdout.strip().splitlines()[-1])
    except (subprocess.SubprocessError, json.JSONDecodeError, IndexError):
        return None


def speed_section(runs: int = 5) -> Section:
    households = benchmark_households()
    s = Section(
        "determinism",
        "Same facts, same answer",
        "Readiness, findings and the plan are computed by deterministic code, so the same accepted facts must always give "
        "the same answer, whatever order they were captured in. Timings are for compile, evaluate, discover and plan together.",
    )
    same_repeat = same_shuffle = 0
    timings: dict[str, list[float]] = {}
    base: dict[str, str] = {}
    for hid in households:
        h = demo_household(hid)
        d1 = digest(h)
        base[hid] = d1
        same_repeat += d1 == digest(demo_household(hid))
        shuffled = h.copy()
        rng = random.Random(hid)
        rng.shuffle(shuffled.claims)
        rng.shuffle(shuffled.entities)
        rng.shuffle(shuffled.sources)
        same_shuffle += digest(shuffled) == d1
        ts = []
        for _ in range(runs):
            t0 = time.perf_counter()
            answer(demo_household(hid))
            ts.append((time.perf_counter() - t0) * 1000)
        timings[hid] = ts
    n = len(households)
    s.metrics.append(ratio("Repeated runs give identical output", same_repeat, n, target_pct=100))
    s.metrics.append(ratio("Shuffled claims, entities and sources give identical output", same_shuffle, n, target_pct=100))
    seeds_ok = seeds_n = 0
    for seed in ("1", "2"):
        child = _child_digests(households, seed)
        if child is None:
            continue
        seeds_n += n
        seeds_ok += sum(1 for hid in households if child.get(hid) == base[hid])
    if seeds_n:
        s.metrics.append(ratio("Fresh processes with different hash seeds agree", seeds_ok, seeds_n, target_pct=100))
    else:
        s.metrics.append(
            Metric("Fresh processes with different hash seeds agree", None, "100%", "not run", "Couldn't start a child process.")
        )
    worst = max(max(v) for v in timings.values())
    med = statistics.median([x for v in timings.values() for x in v])
    s.metrics.append(
        Metric("Engine time per household, median", f"{med:.0f} ms", None, "info", f"{runs} runs per household on this machine.")
    )
    s.metrics.append(
        Metric(
            "Engine time per household, slowest run",
            f"{worst:.0f} ms",
            "≤ 3000 ms",
            "pass" if worst <= 3000 else "fail",
            "Includes an exhaustive plan search.",
        )
    )
    s.details.append("| Household | Median | Slowest | Output hash |")
    s.details.append("|---|---|---|---|")
    for hid, ts in timings.items():
        s.details.append(f"| {hid} | {statistics.median(ts):.0f} ms | {max(ts):.0f} ms | `{base[hid][:12]}` |")
    return s
