"""Analyse a household: compile, evaluate, discover, challenge, plan.

ADK graph:

    START -> compile -> evaluate -> discover --findings--> challenge_prompt -> challenger (agent) -> apply_challenge -> plan
                                             --none------------------------------------------------------------> plan

Every number comes from code. The challenger (Gemini in live mode, a rule-based
reviewer offline) can uphold, narrow or question a finding with cited claims; it
can't add findings, and code rejects anything it cites that isn't in the finding.
If ADK or the model fails, the same steps run as a plain state machine, without
the challenge, and the trace says so.
"""

from __future__ import annotations

from datetime import UTC, datetime

from google.adk import Agent, Event, Workflow

from ..ai import fixture
from ..ai.context import challenge_prompt
from ..ai.llm import generation_config, model_for, prompt
from ..ai.schemas import ChallengeReport
from ..config import get_settings
from ..domain.compile import Compiled
from ..domain.household import Household
from ..engine.discover import Finding, discover
from ..engine.evaluate import ScenarioResult, evaluate
from ..engine.repair import Plan, plan
from ..engine.serialize import finding_dict, plan_dict, result_dict
from .runner import models_used, run_workflow


class AnalysisContext:
    def __init__(self, household: Household, budget_minutes: int | None = None):
        self.h = household
        self.budget = budget_minutes or household.settings.budget_minutes
        self.compiled: Compiled | None = None
        self.result: ScenarioResult | None = None
        self.findings: list[Finding] = []
        self.plan: Plan | None = None
        self.challenge_mode = "none"

    # ------------------------------------------------------------------ steps
    def compile(self) -> dict:
        self.compiled = self.h.compile()
        accepted = sum(1 for c in self.h.claims if c.review == "accepted")
        return {
            "accepted_claims": accepted,
            "responsibilities": len(self.compiled.world.responsibilities),
            "diagnostics": self.compiled.diagnostics,
        }

    def evaluate(self) -> dict:
        c = self.compiled
        self.result = evaluate(c.world, c.scenario)
        s = self.result.summary
        return {
            "ready": s.ready,
            "total": s.total,
            "blocked": s.blocked,
            "needs_confirmation": s.needs_confirmation,
            "needs_handover": s.needs_handover,
        }

    def discover(self) -> dict:
        c = self.compiled
        self.findings = discover(c.world, c.scenario, self.result, c.mentions, c.contradictions)
        return {"findings": len(self.findings), "kinds": sorted({f.kind for f in self.findings})}

    def challenge_prompt(self) -> str:
        return challenge_prompt(self.h, self.findings)

    def offline_challenge(self, text, media) -> ChallengeReport:
        return fixture.offline_challenge(self.findings, {c.id: c for c in self.h.claims})

    def apply_challenge(self, report: ChallengeReport) -> dict:
        by_id = {f.id: f for f in self.findings}
        counts = {"uphold": 0, "narrow": 0, "question": 0, "ignored": 0}
        for item in report.items:
            f = by_id.get(item.finding_id)
            if f is None:
                counts["ignored"] += 1
                continue
            allowed = set(f.claim_ids)
            because = [c for c in item.because_claims if c in allowed]
            weak = [c for c in item.weak_claims if c in allowed]
            drop = [r for r in item.drop if r in f.responsibilities]
            verdict = item.verdict
            if verdict == "narrow" and not (drop and because):
                verdict = "question" if item.question else "uphold"
            f.status = {"uphold": "retained", "narrow": "narrowed", "question": "ask"}[verdict]
            f.challenge = {
                "verdict": verdict,
                "explanation": item.explanation,
                "drop": drop if verdict == "narrow" else [],
                "because_claims": because,
                "weak_claims": weak,
                "question": item.question if verdict == "question" else None,
                "by": "gemini" if get_settings().live else "offline-rules",
            }
            if verdict == "question" and item.question and item.question not in f.questions:
                f.questions.append(item.question)
            counts[verdict] += 1
        for f in self.findings:
            if f.challenge is None:
                f.status = "retained"
        self.challenge_mode = "gemini" if get_settings().live else "offline-rules"
        return counts

    def make_plan(self) -> dict:
        c = self.compiled
        self.plan = plan(c.world, c.scenario, self.result, budget_minutes=self.budget)
        return {"minutes": self.plan.minutes, "steps": len(self.plan.steps), "ready_after": self.plan.after.ready, "label": self.plan.label}

    # ------------------------------------------------------------------ output
    def snapshot(self, trace: list[dict], engine_path: str) -> dict:
        c = self.compiled
        s = get_settings()
        return {
            "world_version": self.h.version,
            "computed_at": datetime.now(UTC).isoformat(),
            "ai_mode": s.ai_mode,
            "models": models_used(trace) if s.live else None,
            "workflow": engine_path,
            "challenge": self.challenge_mode,
            "result": result_dict(c.world, c.scenario, self.result),
            "findings": [finding_dict(c.world, f) for f in self.findings],
            "plan": plan_dict(c.world, c.scenario, self.plan),
            "diagnostics": c.diagnostics,
            "trace": trace,
        }


def build_analysis(ctx: AnalysisContext) -> Workflow:
    challenger = Agent(
        name="challenger",
        model=model_for("challenger", ctx.offline_challenge),
        instruction=prompt("challenger"),
        output_schema=ChallengeReport,
        generate_content_config=generation_config(0.2, thinking="medium"),
    )

    def compile_claims(node_input):
        return ctx.compile()

    def evaluate_scenario(node_input):
        return ctx.evaluate()

    def discover_findings(node_input):
        out = ctx.discover()
        return Event(route=["challenge" if ctx.findings else "skip"], output=out)

    def build_challenge(node_input):
        return ctx.challenge_prompt()

    def apply_challenge(node_input: ChallengeReport):
        return ctx.apply_challenge(node_input)

    def plan_preparation(node_input):
        return ctx.make_plan()

    return Workflow(
        name="analysis",
        edges=[
            ("START", compile_claims, evaluate_scenario, discover_findings),
            (discover_findings, {"challenge": build_challenge, "skip": plan_preparation}),
            (build_challenge, challenger, apply_challenge, plan_preparation),
        ],
    )


def run_state_machine(ctx: AnalysisContext, trace: list[dict], note: str) -> None:
    """Fallback: the same deterministic steps without ADK or the challenger."""
    trace.append({"node": "fallback", "kind": "code", "ms": 0, "summary": note})
    for name, step in (
        ("compile_claims", ctx.compile),
        ("evaluate_scenario", ctx.evaluate),
        ("discover_findings", ctx.discover),
        ("plan_preparation", ctx.make_plan),
    ):
        out = step()
        trace.append(
            {"node": name, "kind": "code", "ms": 0, "summary": ", ".join(f"{k}: {v}" for k, v in out.items() if not isinstance(v, list))}
        )


async def analyse(ctx: AnalysisContext) -> dict:
    trace: list[dict] = []
    path = "adk"
    try:
        await run_workflow(build_analysis(ctx), ctx.h.settings.id, trace)
        if ctx.plan is None:
            raise RuntimeError("the workflow ended early")
    except Exception as exc:  # noqa: BLE001 - any failure falls back to the deterministic path
        path = "state-machine"
        ctx.findings = []
        ctx.challenge_mode = "unavailable"
        run_state_machine(ctx, trace, f"The AI review step failed ({type(exc).__name__}); the engine ran on its own.")
    return ctx.snapshot(trace, path)
