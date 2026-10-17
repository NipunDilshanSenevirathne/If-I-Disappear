"""Section 8: the automated test suite, run as part of the report."""

from __future__ import annotations

import os
import re
import subprocess
import sys

from .common import API, Metric, Section, ratio


def tests_section() -> Section:
    s = Section(
        "tests",
        "Automated tests",
        "The API's unit and integration tests (engine, compiler, quote checks, redaction, workflows in replay mode and the "
        "HTTP API end to end), run with no network and no model.",
    )
    env = dict(os.environ, AI_MODE="fixture")
    env.pop("GEMINI_API_KEY", None)
    env.pop("GOOGLE_API_KEY", None)
    try:
        out = subprocess.run(
            [sys.executable, "-m", "pytest", "-p", "no:cacheprovider"],
            cwd=API,
            capture_output=True,
            text=True,
            env=env,
            timeout=900,
        )
    except subprocess.SubprocessError as exc:
        s.metrics.append(Metric("Tests passing", None, "100%", "not run", f"Couldn't run pytest: {exc}"))
        return s
    text = out.stdout + out.stderr
    passed = int(m.group(1)) if (m := re.search(r"(\d+) passed", text)) else 0
    failed = int(m.group(1)) if (m := re.search(r"(\d+) failed", text)) else 0
    errors = int(m.group(1)) if (m := re.search(r"(\d+) errors?", text)) else 0
    skipped = int(m.group(1)) if (m := re.search(r"(\d+) skipped", text)) else 0
    s.metrics.append(ratio("Tests passing", passed, passed + failed + errors, target_pct=100))
    if skipped:
        s.metrics.append(Metric("Tests skipped", str(skipped), None, "info", "Live tests need GEMINI_API_KEY and network."))
    if failed or errors:
        tail = [line for line in text.splitlines() if line.startswith(("FAILED", "ERROR"))][:20]
        s.details += [f"- {line}" for line in tail]
    return s
