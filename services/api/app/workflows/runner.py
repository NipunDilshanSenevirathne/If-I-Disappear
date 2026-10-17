"""Run an ADK workflow and keep a readable trace of every node.

The trace is shown on the "How it was worked out" screen: which agent or
function ran, in what order, how long it took, what it produced and, for agent
steps, which Google model answered (and which were skipped, and why).
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from google.adk import Runner, Workflow
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel

from ..ai.router import CALLS

APP_NAME = "if-i-disappear"


def summarise(value: Any, limit: int = 240) -> str:
    if value is None:
        return ""
    if isinstance(value, types.Content):  # what is about to be sent to a model
        kinds = ["text" if p.text else (p.inline_data.mime_type if p.inline_data else "other") for p in value.parts or []]
        return ("for the model: " + " + ".join(kinds))[:limit]
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    if isinstance(value, dict):
        parts = []
        for k, v in list(value.items())[:8]:
            if isinstance(v, list):
                parts.append(f"{k}: {len(v)}")
            elif isinstance(v, (str, int, float, bool)) or v is None:
                text = str(v)
                parts.append(f"{k}: {text[:60]}")
        text = ", ".join(parts)
    elif isinstance(value, list):
        text = f"{len(value)} items"
    else:
        text = str(value)
        if text.startswith("TASK:"):
            task = text.split("\n", 1)[0].removeprefix("TASK:").strip()
            text = f"prompt for the {task} step ({len(text)} characters)"
    return text[:limit]


def node_name(path: str | None) -> str:
    if not path:
        return "?"
    last = path.split("/")[-1]
    return last.split("@")[0]


AGENT_NODES = {"listener", "reader", "extractor", "challenger", "grader"}


async def run_workflow(workflow: Workflow, payload: str, trace: list[dict]) -> Any:
    """Run to completion; return the final output. Each node's output is appended to `trace`."""
    calls = CALLS.get()
    token = None
    if calls is None:
        calls = []
        token = CALLS.set(calls)
    seen = len(calls)
    runner = Runner(app_name=APP_NAME, node=workflow, session_service=InMemorySessionService(), auto_create_session=True)
    message = types.Content(role="user", parts=[types.Part(text=payload)])
    final = None
    last = time.perf_counter()
    try:
        async for event in runner.run_async(user_id="pipeline", session_id=uuid.uuid4().hex, new_message=message):
            if event.node_info is None or event.output is None:
                continue
            nowt = time.perf_counter()
            name = node_name(event.node_info.path)
            entry = {
                "node": name,
                "kind": "agent" if name in AGENT_NODES else "code",
                "ms": round((nowt - last) * 1000),
                "summary": summarise(event.output),
            }
            if name in AGENT_NODES and len(calls) > seen:
                call = calls[-1]
                entry["model"] = call.get("model")
                entry["model_label"] = call.get("label")
                entry["cached"] = bool(call.get("cached"))
                entry["skipped"] = call.get("skipped") or []
            seen = len(calls)
            trace.append(entry)
            last = nowt
            final = event.output
    finally:
        if token is not None:
            CALLS.reset(token)
    return final


def models_used(trace: list[dict]) -> list[str]:
    """The Google models that answered in a trace, in order of first use."""
    out: list[str] = []
    for step in trace:
        label = step.get("model_label")
        if label and label not in out:
            out.append(label)
    return out
