"""Grade a teach-back, as a small ADK workflow.

    grade:  START -> grading_prompt -> grader (agent) -> decide

The grader marks each approved step; `decide` (code) turns that into
unassisted / practiced_with_help / not_yet. Offline, or when the free-tier
allowance is used up, the keyword grader stands in and the result says so.
"""

from __future__ import annotations

import uuid
from datetime import date

from google.adk import Agent, Workflow

from ..ai.context import grading_prompt
from ..ai.grading import decide, ground, keyword_grade
from ..ai.llm import generation_config, model_for, prompt
from ..ai.redact import redact
from ..ai.schemas import PracticeGrade
from ..config import get_settings
from ..domain.claims import PracticeAttempt, Procedure
from .runner import run_workflow


class GradeContext:
    def __init__(
        self,
        procedure: Procedure,
        person: str,
        person_name: str,
        transcript: str,
        coach_transcript: str | None = None,
        hints_given: int = 0,
    ):
        self.procedure = procedure
        self.person = person
        self.person_name = person_name
        self.transcript = redact(transcript).text
        self.coach_transcript = redact(coach_transcript).text if coach_transcript else None
        self.hints_given = hints_given
        self.attempt: PracticeAttempt | None = None
        self.ungrounded: list[str] = []  # steps the grader called covered without quoting the learner
        self.grader_model: str | None = None

    def offline_grade(self, text, media) -> PracticeGrade:
        return keyword_grade(self.procedure, self.transcript, self.hints_given)

    def decide(self, grade: PracticeGrade) -> PracticeAttempt:
        # hints counted by the app (text practice) or by the grader (voice practice): take the larger
        grade = grade.model_copy(update={"hints_given": max(grade.hints_given, self.hints_given)})
        grade, self.ungrounded = ground(grade, self.transcript)
        result, covered, missed = decide(self.procedure, grade)
        self.attempt = PracticeAttempt(
            id=f"A-{uuid.uuid4().hex[:8]}",
            person=self.person,
            responsibility=self.procedure.responsibility,
            created=date.today(),
            transcript=self.transcript,
            hints=[f"{grade.hints_given} hint(s)"] if grade.hints_given else [],
            covered=covered,
            missed=missed,
            unsafe=list(grade.unsafe),
            result=result,
            grader="gemini" if get_settings().live else "keyword",
            feedback=grade.feedback,
        )
        return self.attempt


def build_grade(ctx: GradeContext) -> Workflow:
    grader = Agent(
        name="grader",
        model=model_for("grader", ctx.offline_grade),
        instruction=prompt("grader"),
        output_schema=PracticeGrade,
        generate_content_config=generation_config(0.0, thinking="low"),
    )

    def build_prompt(node_input):
        return grading_prompt(ctx.procedure, ctx.person_name, ctx.transcript, ctx.coach_transcript)

    def decide_result(node_input: PracticeGrade):
        a = ctx.decide(node_input)
        return {"result": a.result, "covered": len(a.covered), "missed": len(a.missed)}

    return Workflow(name="grade", edges=[("START", build_prompt, grader, decide_result)])


async def grade_attempt(ctx: GradeContext, trace: list[dict]) -> PracticeAttempt:
    try:
        await run_workflow(build_grade(ctx), ctx.procedure.responsibility, trace)
        model = next((step.get("model_label") for step in trace if step.get("node") == "grader"), None)
        if ctx.attempt is not None and model:
            ctx.attempt.grader = model
    except Exception as exc:  # noqa: BLE001 - fall back to the offline grader, and say so
        from ..ai.router import AIUnavailable

        why = str(exc) if isinstance(exc, AIUnavailable) else f"Grading with the model failed ({type(exc).__name__})"
        trace.append({"node": "fallback", "kind": "code", "ms": 0, "summary": f"{why} Used the keyword grader."})
        ctx.decide(keyword_grade(ctx.procedure, ctx.transcript, ctx.hints_given))
        ctx.attempt.grader = "keyword"
    return ctx.attempt
