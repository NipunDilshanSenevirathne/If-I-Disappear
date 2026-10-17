"""Quote verification: every claim must point at text that really exists.

The extractor (Gemini) must return a verbatim quote for each claim. Models
sometimes paraphrase or invent quotes, so before a claim is shown for review we
check the quote against the stored source text, and record where it was found.
A claim whose quote can't be found is marked `unsupported` and never compiled.

Matching is exact after light normalisation only: Unicode NFC, curly quotes to
straight quotes, dashes to hyphens and collapsed whitespace. No fuzzy matching:
a near-miss is reported as a near-miss, with the closest passage for a human.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from ..domain.claims import Claim, EvidenceRef, Source

_QUOTES = str.maketrans({"‘": "'", "’": "'", "‚": "'", "‛": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "})
_WS = re.compile(r"\s+")


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").translate(_QUOTES)
    return _WS.sub(" ", text).strip()


@dataclass
class _Index:
    """Normalised text plus a map back to positions in the original text."""

    norm: str
    back: list[int]


def _index(text: str) -> _Index:
    text = unicodedata.normalize("NFC", text or "").translate(_QUOTES)
    norm_chars: list[str] = []
    back: list[int] = []
    prev_space = True
    for i, ch in enumerate(text):
        if ch.isspace():
            if prev_space:
                continue
            norm_chars.append(" ")
            back.append(i)
            prev_space = True
        else:
            norm_chars.append(ch)
            back.append(i)
            prev_space = False
    while norm_chars and norm_chars[-1] == " ":
        norm_chars.pop()
        back.pop()
    return _Index("".join(norm_chars), back)


@dataclass
class QuoteCheck:
    source_id: str
    quote: str
    found: bool
    start: int | None = None  # offsets in the original source text
    end: int | None = None
    locator: str | None = None
    field: str = "text"  # text | text_original
    closest: str | None = None
    similarity: float = 0.0


@dataclass
class ClaimCheck:
    claim_id: str
    supported: bool
    checks: list[QuoteCheck] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


def find(source_text: str, quote: str) -> tuple[int, int] | None:
    idx = _index(source_text)
    q = normalise(quote)
    if not q:
        return None
    pos = idx.norm.find(q)
    if pos < 0:
        return None
    start = idx.back[pos]
    end = idx.back[pos + len(q) - 1] + 1
    return start, end


def locate(source: Source, text: str, start: int) -> str:
    """Human-readable location: page and line for documents, sentence for speech."""
    before = text[:start]
    if source.kind in ("voice", "practice"):
        sentence = len(re.findall(r"[.!?](?:\s|$)", before)) + 1
        return f"sentence {sentence}"
    page = None
    for m in re.finditer(r"\[Page (\d+)\]", before):
        page = int(m.group(1))
    line_start = before.rfind("[Page ") if page else -1
    segment = before[line_start:] if line_start >= 0 else before
    line = segment.count("\n") + (0 if page else 1)
    if page:
        return f"page {page}, line {max(1, line)}"
    return f"line {line}"


def _closest(text: str, quote: str) -> tuple[str | None, float]:
    """The passage most like the quote, starting and ending on word boundaries."""
    norm = normalise(text)
    q = normalise(quote)
    if not norm or not q:
        return None, 0.0
    n = len(q)
    starts = [0] + [m.end() for m in re.finditer(r" ", norm)]
    best, best_ratio = None, 0.0
    for i in starts:
        j = min(len(norm), i + n)
        while j < len(norm) and norm[j] != " ":
            j += 1
        window = norm[i:j]
        ratio = SequenceMatcher(None, window, q).ratio()
        if ratio > best_ratio:
            best, best_ratio = window, ratio
    return best, round(best_ratio, 3)


def check_quote(source: Source, ref: EvidenceRef) -> QuoteCheck:
    for field_name in ("text", "text_original"):
        text = getattr(source, field_name) or ""
        hit = find(text, ref.quote)
        if hit:
            return QuoteCheck(source.id, ref.quote, True, hit[0], hit[1], locate(source, text, hit[0]), field_name)
    closest, ratio = _closest(source.text, ref.quote)
    return QuoteCheck(source.id, ref.quote, False, closest=closest, similarity=ratio)


QUOTE_EXEMPT = {"household_review", "external_confirmation"}


def check_claim(claim: Claim, sources: dict[str, Source]) -> ClaimCheck:
    """A claim is supported when every quote is found in its source.

    Household decisions made in the app (derivation household_review) don't need
    a quote: the review itself is the evidence and is logged."""
    result = ClaimCheck(claim.id, True)
    if not claim.evidence:
        if claim.derivation in QUOTE_EXEMPT:
            return result
        result.supported = False
        result.issues.append("No quote was given for this claim.")
        return result
    for ref in claim.evidence:
        source = sources.get(ref.source_id)
        if source is None:
            result.supported = False
            result.issues.append(f"Source {ref.source_id} doesn't exist.")
            continue
        qc = check_quote(source, ref)
        result.checks.append(qc)
        if not qc.found:
            result.supported = False
            near = f' The closest passage is: "{qc.closest.strip()}"' if qc.closest and qc.similarity >= 0.6 else ""
            result.issues.append(f"The quote wasn't found in {ref.source_id}.{near}")
    return result


def with_locators(claim: Claim, sources: dict[str, Source]) -> Claim:
    """Return a copy of the claim with locators filled in from the verified quotes."""
    refs = []
    for ref in claim.evidence:
        source = sources.get(ref.source_id)
        loc = ref.locator
        if source is not None and not loc:
            qc = check_quote(source, ref)
            loc = qc.locator if qc.found else None
        refs.append(EvidenceRef(source_id=ref.source_id, quote=ref.quote, locator=loc))
    return claim.model_copy(update={"evidence": refs})
