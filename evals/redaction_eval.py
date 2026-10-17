"""Section 4: secrets never leave the phone as text.

PINs, passwords, one-time codes, card and account numbers are removed before
anything is stored or sent to a model; phone numbers keep only their last four
digits. Cases are in evals/cases/redaction.yaml.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from app.ai.redact import redact

from .common import Section, ratio

CASES = Path(__file__).resolve().parent / "cases" / "redaction.yaml"


def redaction_section() -> Section:
    cases = yaml.safe_load(CASES.read_text(encoding="utf-8"))
    caught = 0
    misses = []
    for c in cases["secrets"]:
        out = redact(c["text"]).text
        ok = c["secret"] not in out
        caught += ok
        if not ok:
            misses.append(f"- missed secret: {c['text']!r} -> {out!r}")
    kept = 0
    for c in cases["benign"]:
        out = redact(c["text"]).text
        ok = out == c["text"]
        kept += ok
        if not ok:
            misses.append(f"- changed harmless text: {c['text']!r} -> {out!r}")
    masked = 0
    for c in cases["phones"]:
        out = redact(c["text"]).text
        ok = c["hidden"] not in out and c["kept"] in out
        masked += ok
        if not ok:
            misses.append(f"- phone not masked: {c['text']!r} -> {out!r}")
    s = Section(
        "redaction",
        "Secrets never leave the phone as text",
        "Typed text is redacted before anything else happens; transcripts and document readings are redacted again when the "
        "model returns them. Redaction is deliberately conservative: it would rather hide a harmless number than keep a secret.",
    )
    s.metrics.append(ratio("PINs, passwords, codes, card and account numbers removed", caught, len(cases["secrets"]), target_pct=100))
    s.metrics.append(ratio("Harmless sentences left unchanged", kept, len(cases["benign"]), target_pct=100))
    s.metrics.append(ratio("Phone numbers cut to the last four digits", masked, len(cases["phones"]), target_pct=100))
    s.details += misses
    return s
