"""Sections 1 and 2: the engine against hand-written gold, and the knockout ablation."""

from __future__ import annotations

from app.domain.household import demo_household, load_gold
from app.verify.gold import benchmark_households, check_household, run

from .common import Metric, Section, count, ratio


def engine_section() -> Section:
    households = benchmark_households()
    reports = {h: check_household(h) for h in households}
    claims = sum(len(demo_household(h).claims) for h in households)
    resps = sum(len(run(h).result.results) for h in households)

    def tally(kind: str) -> tuple[int, int]:
        cs = [c for r in reports.values() for c in r.of(kind)]
        return sum(1 for c in cs if c.ok), len(cs)

    states_ok, states_n = tally("state")
    first_ok, first_n = tally("first_problem")
    found_ok, gold_n = tally("finding")
    extra = sum(len(r.of("extra_finding")) for r in reports.values())
    produced = sum(len(run(h).findings) for h in households)
    flag_ok, flag_n = tally("must_not_flag")
    plan_ok, plan_n = tally("plan")
    var_ok, var_n = tally("variant")
    other_ok = sum(1 for r in reports.values() for c in r.checks if c.kind in ("summary", "blocked_dates", "occurrences") and c.ok)
    other_n = sum(1 for r in reports.values() for c in r.checks if c.kind in ("summary", "blocked_dates", "occurrences"))

    s = Section(
        "engine",
        "The engine against hand-written answers",
        f"{len(households)} synthetic households ({', '.join(households)}), {resps} responsibilities and {claims} claims. "
        "Each household was written as a story first: sources, then claims that quote them word for word, then what "
        "the engine should conclude (gold.yaml), before the engine was run on it. They were written by the people who built "
        "the engine, so they test its reasoning on varied situations (migration, a hospital stay; Sri Lanka and the "
        "Philippines), not the messiness of real households. Every number below is recomputed on each run.",
    )
    s.metrics += [
        ratio("Readiness states match", states_ok, states_n, target_pct=100),
        ratio("First problem date matches", first_ok, first_n, target_pct=100),
        ratio(
            "Gold findings found (recall)", found_ok, gold_n, target_pct=100, note="Same id, kind and responsibilities as the gold finding."
        ),
        ratio(
            "Findings that are in the gold set (precision)",
            produced - extra,
            produced,
            target_pct=100,
            note="A finding the gold file doesn't list counts against precision.",
        ),
        ratio("Responsibilities that must not be flagged, left alone", flag_ok, flag_n, target_pct=100),
        ratio("Summary counts and blocked dates match", other_ok, other_n, target_pct=100),
        ratio("Plan matches the hand-written plan (Perera)", plan_ok, plan_n, target_pct=100),
        ratio("What-if variants behave as written (Perera)", var_ok, var_n, target_pct=100),
    ]
    s.details.append("| Household | States | Findings found | Extra findings | Must-not-flag |")
    s.details.append("|---|---|---|---|---|")
    for h, r in reports.items():
        st = r.of("state")
        fd = r.of("finding")
        mn = r.of("must_not_flag")
        s.details.append(
            f"| {h} | {sum(c.ok for c in st)}/{len(st)} | {sum(c.ok for c in fd)}/{len(fd)} | {len(r.of('extra_finding'))} | "
            f"{sum(c.ok for c in mn)}/{len(mn)} |"
        )
    failures = [c.describe() for r in reports.values() for c in r.checks if not c.ok]
    if failures:
        s.details.append("")
        s.details.append("Failures:")
        s.details += [f"- {f}" for f in failures]
    return s


def ablation_section() -> Section:
    """Association alone (a resource that shows up next to several responsibilities)
    versus association plus the counterfactual knockout the engine runs."""
    linked = gold_kept = engine_kept = engine_correct = set_aside_ok = set_aside_n = 0
    rows = []
    for h in benchmark_households():
        gold = load_gold(h)
        findings = {f.id: f for f in run(h).findings}
        for g in gold.get("findings") or []:
            if g["kind"] != "SHARED_DEPENDENCY":
                continue
            f = findings.get(g["id"])
            if f is None:
                continue
            links = {c.responsibility: c for c in f.considered}
            kept = {r for r, c in links.items() if c.verdict == "retained"}
            truth = set(g["retained"])
            linked += len(links)
            gold_kept += len(truth & set(links))
            engine_kept += len(kept)
            engine_correct += len(kept & truth)
            aside = set(g.get("set_aside") or {})
            set_aside_n += len(aside)
            set_aside_ok += len(aside & (set(links) - kept))
            rows.append(f"| {h} | {g['id']} | {len(links)} | {len(truth)} | {len(kept)} | {len(kept & truth)} |")
    s = Section(
        "ablation",
        "Why the knockout test matters",
        "A resource that appears next to several responsibilities is only a candidate. Association alone would warn about "
        "every link; the engine re-runs the absence as if the resource were still available to everyone at home and keeps "
        "only the links where that changes the outcome (or where it is the only reminder).",
    )
    s.metrics += [
        ratio("Association only: links that really matter (precision)", gold_kept, linked, note="Every linked responsibility is flagged."),
        ratio("Association + knockout: links kept that really matter (precision)", engine_correct, engine_kept, target_pct=100),
        ratio("Association + knockout: links that matter, kept (recall)", engine_correct, gold_kept, target_pct=100),
        ratio("False alarms correctly set aside", set_aside_ok, set_aside_n, target_pct=100),
    ]
    s.details.append("| Household | Finding | Links | Gold: matter | Engine kept | Correct |")
    s.details.append("|---|---|---|---|---|---|")
    s.details += rows
    return s


__all__ = ["Metric", "ablation_section", "count", "engine_section"]
