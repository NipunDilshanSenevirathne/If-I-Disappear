"""Models for the ADK agents: routed Google models in live mode, a replay model offline.

Both modes run the *same* ADK workflows. In live mode every agent gets a
`RoutedGemini`, which sends each request through the free-tier model router
(app/ai/router.py). In fixture mode a `ReplayLlm` stands in for Gemini and
answers from a responder function (the reviewed sample data, a rule-based
reviewer, the keyword grader). The interface always says which mode is on.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import AsyncGenerator, Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from google.adk.models import BaseLlm, LlmRequest, LlmResponse
from google.genai import types
from pydantic import BaseModel, ConfigDict

from ..config import get_settings

PROMPTS = Path(__file__).resolve().parent / "prompts"

Responder = Callable[[str, list[types.Part]], Any]


@lru_cache
def _prompt_text(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def prompt(name: str, **values: Any) -> str:
    """Load a system instruction and fill {placeholders} (other braces are left alone)."""
    text = _prompt_text(name)
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    return text


def request_text(llm_request: LlmRequest) -> tuple[str, list[types.Part]]:
    texts: list[str] = []
    media: list[types.Part] = []
    for content in llm_request.contents or []:
        for part in content.parts or []:
            if part.text:
                texts.append(part.text)
            elif part.inline_data is not None:
                media.append(part)
    return "\n".join(texts), media


def header(text: str, key: str) -> str | None:
    """Read a 'KEY: value' line from a prompt (used by the replay model)."""
    m = re.search(rf"^{re.escape(key)}:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else None


class ReplayLlm(BaseLlm):
    """A stand-in model that answers from a responder function. No network."""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    model: str = "replay"
    responder: Any = None

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
        text, media = request_text(llm_request)
        answer = self.responder(text, media) if self.responder else {}
        if isinstance(answer, BaseModel):
            payload = answer.model_dump_json()
        elif isinstance(answer, (dict, list)):
            payload = json.dumps(answer, ensure_ascii=False)
        else:
            payload = str(answer)
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=payload)]))


def ensure_env() -> None:
    """ADK's Gemini model reads its credentials from the environment. The SDK accepts
    GEMINI_API_KEY or GOOGLE_API_KEY itself, so the key is not copied between them (setting
    both makes the SDK warn on every call). Only the Vertex AI settings need filling in."""
    s = get_settings()
    if s.use_vertex:
        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
        if s.project:
            os.environ.setdefault("GOOGLE_CLOUD_PROJECT", s.project)
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", s.location)


def model_for(role: str, responder: Responder | None) -> BaseLlm:
    """The model an agent should use. Live: a RoutedGemini for this step. Fixture: a ReplayLlm."""
    s = get_settings()
    if s.live:
        ensure_env()
        from .router import RoutedGemini, chain_for

        first = chain_for(role)[0].model
        return RoutedGemini(model=first, role=role)
    return ReplayLlm(responder=responder)


def generation_config(temperature: float = 0.1, *, thinking: str | None = None) -> types.GenerateContentConfig:
    cfg = types.GenerateContentConfig(temperature=temperature)
    if thinking and get_settings().live:
        cfg.thinking_config = types.ThinkingConfig(thinking_level=thinking)
    return cfg


def genai_client():
    """A google-genai client for direct calls (Live API tokens)."""
    from google import genai

    s = get_settings()
    if s.use_vertex:
        return genai.Client(vertexai=True, project=s.project, location=s.location)
    return genai.Client(api_key=s.gemini_api_key)
