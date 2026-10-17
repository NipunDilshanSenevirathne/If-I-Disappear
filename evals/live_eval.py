"""Section 7: Gemini on the benchmark sources (only with --live and a key).

For each benchmark household we start from the same people, tasks and things
but no claims, send every source's text through the real ingest workflow
(Gemini extractor, then the quote verifier), and compare what comes back with
the hand-written claims. Then we accept every claim that passed the quote check,
with no human edits, and see how many gold findings the engine still reaches.
That last number is the honest end-to-end score: it is what a household would get
if it accepted everything without reading it.

Without --live, or without a key, every metric here is reported as "not run".
"""

from __future__ import annotations

import asyncio
import statistics
import time

from app.config import get_settings
from app.domain.claims import Claim
from app.domain.household import Household, demo_household, load_gold
from app.engine.discover import discover
from app.engine.evaluate import evaluate
from app.verify.gold import benchmark_households
from app.workflows.ingest import IngestContext, ingest_source

from .common import Metric, Section, not_run, ratio

VALUE_KEYS = {"CAN_DO", "FACT", "IMPORTANCE"}


def claim_key(c: Claim, strict: bool = True) -> tuple:
    base = (c.predicate, c.subject, c.object or "")
    if not strict:
        return base
    extra: tuple = ()
    if c.predicate in VALUE_KEYS:
        extra = ((c.value or "").strip().lower(),)
    elif c.predicate == "SCHEDULE" and c.schedule:
        extra = (c.schedule.freq, tuple(sorted(c.schedule.weekdays)), c.schedule.monthday, c.schedule.interval)
    elif c.predicate in ("ROUTE_WINDOW", "BUSY") and c.window:
        extra = (c.window.start, c.window.end)
    elif c.predicate in ("VALID_UNTIL", "UNAVAILABLE") and c.date:
        extra = (c.date.isoformat(),)
    return base + extra


async def _extract(hid: str) -> tuple[Household, list[dict]]:
    gold = demo_household(hid)
    blank = gold.copy()
    blank.claims = []
    rows = []
    for src in sorted(gold.sources, key=lambda s: s.id):
        source = src.model_copy(deep=True)
        source.status = "processing"
        blank.sources = [s for s in blank.sources if s.id != source.id] + [source]
        ctx = IngestContext(blank, source)
        t0 = time.perf_counter()
        trace: list[dict] = []
        try:
            try:
                out = await ingest_source(ctx, trace)
            except Exception as exc:  # noqa: BLE001
                # A per-minute limit or a passing server error isn't a verdict on the model's
                # reading: wait for the next minute and try that source once more.
                if not any(w in str(exc) for w in ("busy this minute", "slow down", "Google had a problem", "took longer")):
                    raise
                await asyncio.sleep(61)
                source.status = "processing"
                ctx = IngestContext(blank, source)
                trace = []
                out = await ingest_source(ctx, trace)
            models = [t.get("model_label") or "no model" for t in trace if t.get("kind") == "agent"]
            rows.append(
                {"source": source.id, "ok": True, "ms": (time.perf_counter() - t0) * 1000, "added": out.get("added", 0), "models": models}
            )
        except Exception as exc:  # noqa: BLE001 - record and carry on
            rows.append(
                {"source": source.id, "ok": False, "ms": (time.perf_counter() - t0) * 1000, "error": f"{type(exc).__name__}: {exc}"[:200]}
            )
    return blank, rows


def _findings_recovered(hid: str, extracted: Household) -> tuple[int, int, int, int]:
    gold = load_gold(hid)
    accepted = extracted.copy()
    for c in accepted.claims:
        if c.verified:
            c.review = "accepted"
    comp = accepted.compile()
    result = evaluate(comp.world, comp.scenario)
    findings = {f.id: f for f in discover(comp.world, comp.scenario, result, comp.mentions, comp.contradictions)}
    found = 0
    for g in gold.get("findings") or []:
        f = findings.get(g["id"])
        if f and f.kind == g["kind"] and ("responsibilities" not in g or sorted(f.responsibilities) == sorted(g["responsibilities"])):
            found += 1
    states = (gold.get("stages") or {}).get("capture", {}).get("states", {})
    right = sum(1 for rid, st in states.items() if rid in result.results and result.results[rid].state.value == st)
    return found, len(gold.get("findings") or []), right, len(states)


def live_section(enabled: bool) -> Section:
    s = Section(
        "live",
        "Gemini on the benchmark sources",
        "Every source's text goes through the real ingest workflow (Gemini extracts claims, code checks every quote), and "
        "the result is compared with the hand-written claims. Then every claim that passed the quote check is accepted "
        "without edits, and the engine runs on that.",
    )
    settings = get_settings()
    why = None
    if not enabled:
        why = "Run with --live (make eval-live) to call Gemini; it is off by default because it costs quota."
    elif not settings.live:
        why = "No GEMINI_API_KEY (or Vertex AI project) is configured, so Gemini wasn't called."
    names = [
        ("Claims Gemini extracted that match a hand-written claim (precision)", "≥ 70%"),
        ("Hand-written claims Gemini found (recall)", "≥ 70%"),
        ("Same, ignoring values and times (recall)", "≥ 80%"),
        ("Extracted claims whose quotes are found word for word", "≥ 90%"),
        ("Gold findings reached with no human edits", "≥ 70%"),
        ("Readiness states right with no human edits", "≥ 70%"),
        ("Sources processed without an error", "100%"),
        ("Time per source, median", None),
        ("Time per source, slowest", None),
    ]
    if why:
        s.metrics += [not_run(n, why, t) for n, t in names]
        return s

    from app.ai.quota import label
    from app.ai.router import chain_for

    chain = " → ".join(label(link.model) for link in chain_for("extractor"))
    s.summary += f" Extraction chain: {chain} (free-tier router), via {'Vertex AI' if settings.use_vertex else 'the Gemini API'}."
    tp = n_extracted = n_gold = 0
    tp_loose = n_gold_loose = 0
    verified = total = 0
    found = gold_n = right = states_n = 0
    rows_all: list[dict] = []

    async def every_household() -> dict:
        # one event loop for the whole run, so the SDK's connections close cleanly
        return {hid: await _extract(hid) for hid in benchmark_households()}

    extracted_all = asyncio.run(every_household())
    for hid in benchmark_households():
        extracted, rows = extracted_all[hid]
        rows_all += [dict(r, household=hid) for r in rows]
        gold_claims = [c for c in demo_household(hid).claims if c.review == "accepted"]
        got = [c for c in extracted.claims if c.review not in ("withdrawn", "superseded")]
        total += len(got)
        verified += sum(1 for c in got if c.verified)
        gk = {claim_key(c) for c in gold_claims}
        ek = {claim_key(c) for c in got}
        tp += len(gk & ek)
        n_extracted += len(ek)
        n_gold += len(gk)
        gl = {claim_key(c, strict=False) for c in gold_claims}
        el = {claim_key(c, strict=False) for c in got}
        tp_loose += len(gl & el)
        n_gold_loose += len(gl)
        f, fn, r, rn = _findings_recovered(hid, extracted)
        found, gold_n, right, states_n = found + f, gold_n + fn, right + r, states_n + rn
        s.details.append(
            f"- {hid}: {len(gk & ek)}/{len(gk)} claims matched, {len(ek)} distinct extracted, gold findings reached {f}/{fn}, states {r}/{rn}"
        )
    ok_rows = [r for r in rows_all if r["ok"]]
    times = [r["ms"] for r in ok_rows]
    answered: dict[str, int] = {}
    for r in ok_rows:
        for m in r.get("models") or []:
            answered[m] = answered.get(m, 0) + 1
    if answered:
        s.details.append("- Extractions answered by: " + ", ".join(f"{k} {v}" for k, v in sorted(answered.items(), key=lambda kv: -kv[1])))
    s.metrics += [
        ratio(names[0][0], tp, n_extracted, target_pct=70),
        ratio(names[1][0], tp, n_gold, target_pct=70),
        ratio(names[2][0], tp_loose, n_gold_loose, target_pct=80),
        ratio(names[3][0], verified, total, target_pct=90),
        ratio(
            names[4][0],
            found,
            gold_n,
            target_pct=70,
            note="Every quote-verified claim accepted as is: the worst case of a household that doesn't review.",
        ),
        ratio(names[5][0], right, states_n, target_pct=70),
        ratio(names[6][0], len(ok_rows), len(rows_all), target_pct=100),
        Metric(names[7][0], f"{statistics.median(times) / 1000:.1f} s" if times else "n/a", None, "info"),
        Metric(names[8][0], f"{max(times) / 1000:.1f} s" if times else "n/a", None, "info"),
    ]
    for r in rows_all:
        if not r["ok"]:
            s.details.append(f"- error in {r['household']}/{r['source']}: {r['error']}")
    return s
