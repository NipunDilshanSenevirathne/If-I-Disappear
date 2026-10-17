"""The approved steps for a task: drafted from the household's own facts, edited and
approved by a person, then used for teach-back practice.

The draft is written by code from accepted claims (when it's due, the usual way,
what to take, the key step), so it never contains anything the household hasn't
said. A person edits it and approves it; only approved steps are used to check
an explanation.
"""

from __future__ import annotations

from ..ai.redact import redact
from ..domain.claims import Procedure, ProcedureStep
from ..domain.household import Household
from ..engine.model import Freq, ReqKind, ResourceKind
from ..engine.text import cap, fmt_day
from ..engine.timeutil import occurrence_dates

MAX_STEPS = 12


class StepError(ValueError):
    pass


def draft(h: Household, responsibility: str) -> dict:
    comp = h.compile()
    w, sc = comp.world, comp.scenario
    resp = w.responsibilities.get(responsibility)
    if resp is None:
        raise StepError("There's no such task in this household.")
    steps: list[dict] = []

    def add(text: str, critical: bool = False) -> None:
        text = text.strip()
        if text and all(s["text"].lower() != text.lower() for s in steps) and len(steps) < 8:
            steps.append({"text": text, "critical": critical, "hint": None})

    rec = resp.recurrence
    if rec.freq is not Freq.ONGOING:
        add(f"{cap(resp.label)} {rec.label()}.", critical=True)
    amounts = [c.value for c in h.claims if c.review == "accepted" and c.predicate == "AMOUNT" and c.subject == responsibility and c.value]
    if amounts:
        add(f"The amount is {amounts[-1]}.", critical=True)
    routes = resp.routes
    if routes:
        first = routes[0]
        if not first.id.endswith(":usual"):
            add(f"The usual way: {first.label}.")
        if first.window:
            add(f"Be there between {first.window.start:%H:%M} and {first.window.end:%H:%M}.", critical=True)
        for req in first.requirements:
            res = w.resources.get(req.target)
            label = res.label if res else w.fact_labels.get(req.target, req.target)
            if req.kind is ReqKind.ACCESS and res is not None:
                if res.kind in (ResourceKind.CONTACT, ResourceKind.PHONE_NUMBER):
                    add(f"Have {label} ready.")
                else:
                    add(f"Take {label}.")
            elif req.kind is ReqKind.VALID:
                add(f"Check that {label} is still valid.")
        for other in routes[1:]:
            if not other.id.endswith(":usual"):
                add(f"If that doesn't work: {other.label}.")
    if resp.demo_step:
        add(f"{cap(resp.demo_step)}.", critical=True)
    dates = occurrence_dates(w, sc, resp) if rec.freq is not Freq.ONGOING else []
    when = dates[0] if dates else None
    prompt = f"It's {fmt_day(when)}. Tell me how you'll {resp.label}." if when else f"Tell me how you'll {resp.label}."
    existing = next((p for p in h.procedures if p.responsibility == responsibility), None)
    if existing is not None:
        steps = [{"text": s.text, "critical": s.critical, "hint": s.hint} for s in existing.steps]
        prompt = existing.scenario_prompt or prompt
    return {
        "responsibility": responsibility,
        "label": resp.label,
        "steps": steps,
        "scenario_prompt": prompt,
        "existing": existing is not None,
    }


def save(h: Household, responsibility: str, steps: list[dict], scenario_prompt: str | None) -> Procedure:
    if responsibility not in {e.id for e in h.entities if e.kind == "responsibility"}:
        raise StepError("There's no such task in this household.")
    clean: list[ProcedureStep] = []
    for i, s in enumerate(steps, start=1):
        text = " ".join((s.get("text") or "").split())
        if not text:
            continue
        if len(text) > 300:
            raise StepError("Keep each step under 300 characters.")
        if redact(text).secrets_removed or (s.get("hint") and redact(s["hint"]).secrets_removed):
            raise StepError("Steps can't contain PINs, passwords or account numbers. Say where to find them instead.")
        hint = " ".join((s.get("hint") or "").split())[:200] or None
        clean.append(ProcedureStep(id=f"s{i}", text=text, critical=bool(s.get("critical")), hint=hint))
    if not clean:
        raise StepError("Add at least one step.")
    if len(clean) > MAX_STEPS:
        raise StepError(f"Use at most {MAX_STEPS} steps.")
    if not any(s.critical for s in clean):
        clean[0] = clean[0].model_copy(update={"critical": True})
    prompt = " ".join((scenario_prompt or "").split())[:300]
    if prompt and redact(prompt).secrets_removed:
        raise StepError("The situation can't contain PINs, passwords or account numbers.")
    old = next((p for p in h.procedures if p.responsibility == responsibility), None)
    proc = Procedure(
        responsibility=responsibility,
        version=(old.version + 1) if old else 1,
        approved=True,
        steps=clean,
        scenario_prompt=prompt or (old.scenario_prompt if old else ""),
        scenario_prompts={} if old is None or prompt != old.scenario_prompt else dict(old.scenario_prompts),
    )
    h.procedures = [p for p in h.procedures if p.responsibility != responsibility] + [proc]
    return proc


__all__ = ["MAX_STEPS", "StepError", "draft", "save"]
