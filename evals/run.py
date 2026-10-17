"""Run the evaluation and write evals/reports/latest.json and latest.md.

    python -m evals.run            # everything that needs no model (a few seconds)
    python -m evals.run --live     # also call Gemini on the benchmark sources (needs a key)
    python -m evals.run --no-tests # skip running the test suite

The report is generated, never hand-written: the API serves latest.json at
/api/evals and the web app shows it on the Evaluation page.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from .common import ROOT, Section

REPORTS = ROOT / "evals" / "reports"


def _commit() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or None if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def build(live: bool, tests: bool) -> dict:
    from app.config import get_settings
    from app.engine.model import ENGINE_VERSION, POLICY_VERSION

    from .containment_eval import containment_section
    from .gold_eval import ablation_section, engine_section
    from .live_eval import live_section
    from .quotes_eval import quotes_section
    from .redaction_eval import redaction_section
    from .router_eval import router_section
    from .speed_eval import speed_section
    from .tests_eval import tests_section

    makers = [engine_section, ablation_section, quotes_section, redaction_section, containment_section, router_section, speed_section]
    sections: list[Section] = []
    timings = {}
    for make in makers:
        t0 = time.perf_counter()
        sections.append(make())
        timings[make.__name__] = round(time.perf_counter() - t0, 2)
    t0 = time.perf_counter()
    sections.append(live_section(live))
    timings["live_section"] = round(time.perf_counter() - t0, 2)
    if tests:
        t0 = time.perf_counter()
        sections.append(tests_section())
        timings["tests_section"] = round(time.perf_counter() - t0, 2)

    metrics = [m for s in sections for m in s.metrics]
    s = get_settings()
    return {
        "generated": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": _commit(),
        "ai_mode": s.ai_mode if live else "none (no model calls)",
        "engine": ENGINE_VERSION,
        "policy": POLICY_VERSION,
        "python": platform.python_version(),
        "totals": {
            "pass": sum(1 for m in metrics if m.status == "pass"),
            "fail": sum(1 for m in metrics if m.status == "fail"),
            "not_run": sum(1 for m in metrics if m.status == "not run"),
            "info": sum(1 for m in metrics if m.status == "info"),
        },
        "seconds": timings,
        "sections": [x.to_dict() for x in sections],
    }


def to_markdown(report: dict) -> str:
    t = report["totals"]
    lines = [
        "# Evaluation report",
        "",
        f"Generated {report['generated']} by `python -m evals.run`"
        + (f" at commit `{report['commit']}`" if report.get("commit") else "")
        + f". Versions: {report['engine']}, {report['policy']}, Python {report['python']}. AI: {report['ai_mode']}.",
        "",
        f"**{t['pass']} passed, {t['fail']} failed, {t['not_run']} not run**, {t['info']} for information.",
        "",
        "This file is generated. Don't edit it by hand; run the harness again.",
        "",
    ]
    for sec in report["sections"]:
        lines += [f"## {sec['title']}", "", sec["summary"], "", "| Metric | Result | Target | Status |", "|---|---|---|---|"]
        for m in sec["metrics"]:
            value = "not run" if m.get("value") is None else m["value"]
            note = f"<br><sub>{m['note']}</sub>" if m.get("note") else ""
            lines.append(f"| {m['name']}{note} | {value} | {m.get('target') or ''} | {m['status']} |")
        if sec.get("details"):
            lines += [""] + sec["details"]
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", action="store_true", help="also call Gemini on the benchmark sources (needs GEMINI_API_KEY)")
    ap.add_argument("--no-tests", action="store_true", help="don't run the pytest suite")
    ap.add_argument("--out", type=Path, default=REPORTS)
    args = ap.parse_args(argv)
    report = build(live=args.live, tests=not args.no_tests)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "latest.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (args.out / "latest.md").write_text(to_markdown(report), encoding="utf-8")
    t = report["totals"]
    print(f"{t['pass']} passed, {t['fail']} failed, {t['not_run']} not run, {t['info']} info -> {args.out / 'latest.md'}")
    for sec in report["sections"]:
        for m in sec["metrics"]:
            if m["status"] == "fail":
                print(f"  FAIL {sec['title']}: {m['name']} = {m.get('value')} (target {m.get('target')})")
    return 1 if t["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
