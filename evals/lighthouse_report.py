"""Lighthouse scores for the main pages, phone and desktop -> evals/reports/lighthouse.md (+ .json).

    python -m evals.lighthouse_report [BASE_URL]        (default http://localhost:8080)

Needs the app running (`make serve`) and Node. Lighthouse is run with `npx lighthouse@12.8.2`
unless LIGHTHOUSE_CLI points at a local `lighthouse/cli/index.js`. Chrome comes from CHROME_PATH
(Playwright's Chromium works). Nothing here is typed in by hand: every number is read from
Lighthouse's own JSON output.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

VERSION = "12.8.2"
PAGES = [
    ("landing", "Landing", "/"),
    ("overview", "Household overview (sample family)", "/demo"),
    ("evals", "Evaluation report", "/evals"),
    ("start", "Start your own household", "/start"),
]
FORMS = ("mobile", "desktop")
OUT = Path(__file__).resolve().parent / "reports"


def lighthouse_cmd() -> list[str]:
    cli = os.getenv("LIGHTHOUSE_CLI")
    if cli:
        return ["node", cli]
    npx = shutil.which("npx")
    if not npx:
        sys.exit("Needs Node (npx) or LIGHTHOUSE_CLI.")
    return [npx, "--yes", f"lighthouse@{VERSION}"]


def chrome_path() -> str | None:
    for p in (os.getenv("CHROME_PATH"), os.getenv("CHROMIUM_PATH"), "/opt/pw-browsers/chromium"):
        if p and Path(p).exists():
            return p
    return None


def run(base: str) -> dict:
    env = dict(os.environ)
    chrome = chrome_path()
    if chrome:
        env["CHROME_PATH"] = chrome
    results: dict = {"base": base, "lighthouse": None, "runs": []}
    with tempfile.TemporaryDirectory() as tmp:
        for key, label, path in PAGES:
            for form in FORMS:
                out = Path(tmp) / f"{key}-{form}.json"
                cmd = [*lighthouse_cmd(), base.rstrip("/") + path, "--output=json", f"--output-path={out}", "--quiet"]
                cmd.append("--chrome-flags=--headless=new --no-sandbox --disable-gpu")
                if form == "desktop":
                    cmd.append("--preset=desktop")
                done = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
                if done.returncode != 0 or not out.exists():
                    results["runs"].append({"page": key, "label": label, "form": form, "error": (done.stderr or "failed")[-300:]})
                    print(f"failed: {key} {form}", file=sys.stderr)
                    continue
                d = json.loads(out.read_text())
                a = d["audits"]
                results["lighthouse"] = d.get("lighthouseVersion")
                results["runs"].append(
                    {
                        "page": key,
                        "label": label,
                        "form": form,
                        "scores": {k: round(v["score"] * 100) for k, v in d["categories"].items() if v.get("score") is not None},
                        "fcp_s": round(a["first-contentful-paint"]["numericValue"] / 1000, 1),
                        "lcp_s": round(a["largest-contentful-paint"]["numericValue"] / 1000, 1),
                        "tbt_ms": round(a["total-blocking-time"]["numericValue"]),
                        "cls": round(a["cumulative-layout-shift"]["numericValue"], 3),
                        "kib": round(a["total-byte-weight"]["numericValue"] / 1024),
                    }
                )
                print(f"ok: {key} {form}")
    return results


def render(r: dict) -> str:
    when = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()
    lines = [
        "# Lighthouse",
        "",
        f"Generated {when} by `python -m evals.lighthouse_report` with Lighthouse {r['lighthouse'] or VERSION}, against "
        f"{r['base']}. Phone runs use Lighthouse's default emulation (a mid-range phone on slow 4G with a 4× slower CPU, "
        "simulated); desktop runs use its desktop preset. Scores are out of 100.",
        "",
        "| Page | Form | Performance | Accessibility | Best practices | SEO | First paint | Largest paint | Blocking time | Layout shift | Downloaded |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for x in r["runs"]:
        if "error" in x:
            lines.append(f"| {x['label']} | {x['form']} | not run: {x['error'].splitlines()[-1][:80]} | | | | | | | | |")
            continue
        s = x["scores"]
        lines.append(
            f"| {x['label']} | {x['form']} | **{s.get('performance', '—')}** | {s.get('accessibility', '—')} | {s.get('best-practices', '—')} | "
            f"{s.get('seo', '—')} | {x['fcp_s']} s | {x['lcp_s']} s | {x['tbt_ms']} ms | {x['cls']} | {x['kib']} KiB |"
        )
    lines += [
        "",
        "A deployed Cloud Run service adds the network between the phone and Google's edge, and a cold start adds "
        "a few seconds to the first visit (none with `MIN_INSTANCES=1`).",
        "",
        "This file is generated. Run `make lighthouse` (with the app running) to refresh it.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
    r = run(base)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "lighthouse.json").write_text(json.dumps(r, indent=2) + "\n")
    (OUT / "lighthouse.md").write_text(render(r))
    print(f"wrote {OUT / 'lighthouse.md'}")


if __name__ == "__main__":
    main()
