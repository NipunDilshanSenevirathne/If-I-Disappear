"""Section 3: quotes. Every claim must point at text that is really in the source.

We check every quote in every benchmark household, then perturb each one the way
a model might (a changed number, a changed word, an inserted 'not', two words
swapped, or the right words attributed to the wrong source) and check that the
verifier rejects the perturbed quote. Harmless formatting differences (curly
apostrophes, extra spaces, other dash characters, decomposed Unicode) must still
be accepted.
"""

from __future__ import annotations

import re
import unicodedata

from app.domain.claims import EvidenceRef
from app.domain.household import demo_household
from app.verify.gold import benchmark_households
from app.verify.quotes import QUOTE_EXEMPT, check_claim

from .common import Section, ratio


def _digit(q: str) -> str | None:
    m = re.search(r"\d", q)
    if not m:
        return None
    d = str((int(m.group()) + 1) % 10)
    return q[: m.start()] + d + q[m.end() :]


def _word(q: str) -> str | None:
    words = [m for m in re.finditer(r"[A-Za-z]{4,}", q)]
    if not words:
        return None
    m = max(words, key=lambda x: (len(x.group()), -x.start()))
    replacement = "seldom" if m.group().lower() != "seldom" else "always"
    return q[: m.start()] + replacement + q[m.end() :]


def _negation(q: str) -> str | None:
    parts = q.split(" ")
    if len(parts) < 3:
        return None
    return " ".join(parts[:2] + ["not"] + parts[2:])


def _swap(q: str) -> str | None:
    parts = q.split(" ")
    if len(parts) < 4:
        return None
    i = len(parts) // 2
    if parts[i] == parts[i + 1]:
        return None
    parts[i], parts[i + 1] = parts[i + 1], parts[i]
    return " ".join(parts)


PERTURB = {
    "changed number": _digit,
    "changed word": _word,
    "inserted 'not'": _negation,
    "two words swapped": _swap,
}


def _benign(q: str) -> dict[str, str]:
    out = {}
    if "'" in q:
        out["curly apostrophes"] = q.replace("'", "’")
    if " " in q:
        out["extra spaces and a line break"] = q.replace(" ", "  ", 1).replace(" ", "\n", 1)
    if "-" in q:
        out["en dash for hyphen"] = q.replace("-", "–")
    nfd = unicodedata.normalize("NFD", q)
    if nfd != q:
        out["decomposed Unicode"] = nfd
    return out


def _present(text: str | None, quote: str) -> bool:
    """Independent oracle: is this exact wording in the text, allowing only for
    different whitespace? (Deliberately not the verifier's own code.)"""
    if not text:
        return False
    pattern = r"\s+".join(re.escape(w) for w in quote.split())
    return re.search(pattern, text) is not None


def _with_quote(claim, source_id: str, quote: str):
    return claim.model_copy(update={"evidence": [EvidenceRef(source_id=source_id, quote=quote)], "derivation": "user_statement"})


def quotes_section() -> Section:
    total_claims = supported = exempt = 0
    rejected = {k: 0 for k in PERTURB}
    tried = {k: 0 for k in PERTURB}
    near = near_n = 0
    cross_tried = cross_rejected = 0
    benign_tried = benign_ok = 0
    for hid in benchmark_households():
        h = demo_household(hid)
        sources = h.source_map()
        for c in h.claims:
            total_claims += 1
            if c.derivation in QUOTE_EXEMPT:
                exempt += 1
                continue
            if check_claim(c, sources).supported:
                supported += 1
            for ev in c.evidence:
                src = sources.get(ev.source_id)
                if src is None or not _present(src.text, ev.quote):
                    continue
                for name, fn in PERTURB.items():
                    p = fn(ev.quote)
                    if p is None or _present(src.text, p) or _present(src.text_original, p):
                        continue  # no change, or the new wording genuinely exists in the source
                    tried[name] += 1
                    result = check_claim(_with_quote(c, src.id, p), sources)
                    if not result.supported:
                        rejected[name] += 1
                        near_n += 1
                        near += 1 if any(q.closest and q.similarity >= 0.8 for q in result.checks) else 0
                other = next(
                    (
                        x
                        for x in sources.values()
                        if x.id != src.id and not _present(x.text, ev.quote) and not _present(x.text_original, ev.quote)
                    ),
                    None,
                )
                if other is not None:
                    cross_tried += 1
                    cross_rejected += 0 if check_claim(_with_quote(c, other.id, ev.quote), sources).supported else 1
                for b in _benign(ev.quote).values():
                    benign_tried += 1
                    benign_ok += 1 if check_claim(_with_quote(c, src.id, b), sources).supported else 0
    s = Section(
        "quotes",
        "Quotes: the AI can't put words in your mouth",
        "Every claim has to quote its source word for word before a household can review it. Matching is exact after light "
        "normalisation only (Unicode form, quote and dash characters, whitespace); there is no fuzzy matching. Each real quote "
        "is perturbed the way a model might misquote, and run through the same verifier the app uses.",
    )
    s.metrics.append(ratio("Benchmark claims whose quotes are found in their sources", supported, total_claims - exempt, target_pct=100))
    for name in PERTURB:
        s.metrics.append(ratio(f"Misquote rejected: {name}", rejected[name], tried[name], target_pct=100))
    s.metrics.append(ratio("Right words, wrong source: rejected", cross_rejected, cross_tried, target_pct=100))
    s.metrics.append(ratio("Harmless formatting differences still accepted", benign_ok, benign_tried, target_pct=100))
    s.metrics.append(
        ratio(
            "Rejected misquotes shown with the passage they probably meant",
            near,
            near_n,
            note="The reviewer sees the closest passage (similarity at least 0.8) next to the rejected quote.",
        )
    )
    if exempt:
        s.details.append(f"{exempt} claims are household decisions or outside confirmations and carry no quote.")
    return s
