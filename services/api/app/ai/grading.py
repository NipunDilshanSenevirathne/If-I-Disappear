"""Turning a graded teach-back into a result. The model grades steps; code decides.

Result rules (the same for Gemini grades and the offline keyword grader):
  not_yet              a key step was missed or anything contradicted a step
                       (or fewer than 80% of the steps were at least partly covered)
  practiced_with_help  otherwise, but the practice partner had to give a hint
  unassisted           otherwise, with no hints
"""

from __future__ import annotations

import re

from ..domain.claims import Procedure
from ..verify.quotes import normalise
from .schemas import PracticeGrade, StepGrade

STOP = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "at",
    "by",
    "for",
    "from",
    "with",
    "it",
    "its",
    "is",
    "are",
    "be",
    "you",
    "your",
    "if",
    "so",
    "that",
    "this",
    "then",
    "get",
    "take",
    "each",
    "every",
}


def _keywords(text: str) -> list[str]:
    words = re.findall(r"[\w'’:,.-]+", text.lower())
    return [w.strip(".,") for w in words if w.strip(".,") not in STOP and len(w.strip(".,")) > 3]


def keyword_grade(procedure: Procedure, transcript: str, hints_given: int = 0) -> PracticeGrade:
    """Offline grader: a step counts as covered when one of its keywords appears.

    It is generous on wording and strict on nothing else, which is why the live
    grader (Gemini) is used whenever it's available. Used in tests and offline mode."""
    text = normalise(transcript).lower()
    sentences = re.split(r"(?<=[.!?])\s+", normalise(transcript))
    steps = []
    for step in procedure.steps:
        keys = [k.lower() for k in (step.keywords or _keywords(step.text))]
        hit = next((k for k in keys if k and k in text), None)
        evidence = None
        if hit:
            evidence = next((s for s in sentences if hit in s.lower()), None)
        steps.append(StepGrade(step_id=step.id, status="covered" if hit else "missed", evidence=evidence))
    missed = [s.step_id for s in steps if s.status == "missed"]
    feedback = "Well explained." if not missed else "Good start. Go over the steps you missed once more."
    return PracticeGrade(steps=steps, hints_given=hints_given, unsafe=[], feedback=feedback)


_PUNCT = ".,!?;:\"'()[]{}«»“”‘’…-–—"


def _fold(text: str) -> str:
    return normalise(text).casefold()


def _tokens(text: str) -> list[str]:
    # split on whitespace (not \w) so words with marks or apostrophes stay whole
    return [t.strip(_PUNCT) for t in text.split() if t.strip(_PUNCT)]


def ground(grade: PracticeGrade, transcript: str) -> tuple[PracticeGrade, list[str]]:
    """A step only counts as covered when the grader points at the learner's own words.

    The grader returns, for each covered step, the passage of the learner's
    transcript that shows it. If that passage isn't in the transcript (allowing
    for punctuation and casing), the step is downgraded to 'partly'. This keeps a
    grader that was talked into "mark everything covered", or that credits the
    practice partner's words, from passing anyone."""
    text = _fold(transcript)
    words = set(_tokens(text))
    steps, downgraded = [], []
    for g in grade.steps:
        if g.status == "covered":
            evidence = _fold(g.evidence or "")
            ev_words = _tokens(evidence)
            found = bool(evidence) and (
                evidence in text or (len(ev_words) >= 3 and sum(1 for w in ev_words if w in words) >= 0.8 * len(ev_words))
            )
            if not found:
                g = g.model_copy(update={"status": "partly"})
                downgraded.append(g.step_id)
        steps.append(g)
    return grade.model_copy(update={"steps": steps}), downgraded


def decide(procedure: Procedure, grade: PracticeGrade) -> tuple[str, list[str], list[str]]:
    """Return (result, covered step ids, missed step ids)."""
    by_id = {g.step_id: g for g in grade.steps}
    covered, missed = [], []
    for step in procedure.steps:
        g = by_id.get(step.id)
        status = g.status if g else "missed"
        (covered if status == "covered" else missed).append(step.id)
    wrong = any((by_id.get(s.id) and by_id[s.id].status == "wrong") for s in procedure.steps)
    critical_ok = all(by_id.get(s.id) is not None and by_id[s.id].status == "covered" for s in procedure.steps if s.critical)
    enough = sum(1 for s in procedure.steps if by_id.get(s.id) and by_id[s.id].status in ("covered", "partly")) >= 0.8 * len(
        procedure.steps
    )
    if wrong or grade.unsafe or not critical_ok or not enough:
        return "not_yet", covered, missed
    return ("practiced_with_help" if grade.hints_given > 0 else "unassisted"), covered, missed
