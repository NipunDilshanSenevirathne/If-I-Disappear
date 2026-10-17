"""Gemini Live for spoken practice, without exposing the API key.

The browser never sees the API key. It asks this API for an ephemeral token
that can open exactly one Live session, within two minutes, for 30 minutes,
with the model and the practice partner's instructions locked in. The browser
then talks to Gemini directly (low latency), and sends the transcripts back here
for grading. The grade is decided by code, not by the voice session.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from google.genai import types

from ..config import get_settings
from ..domain.claims import Procedure
from .llm import genai_client, prompt


def coach_instruction(procedure: Procedure, person: str, leaver: str, responsibility_label: str, scenario: str) -> str:
    steps = "\n".join(f"- {s.text}" + (" (key step)" if s.critical else "") for s in procedure.steps)
    return prompt(
        "coach",
        person=person,
        leaver=leaver,
        responsibility=responsibility_label,
        scenario=scenario,
        steps=steps,
    )


def create_token(system_instruction: str) -> dict:
    s = get_settings()
    if not s.live:
        raise RuntimeError("Spoken practice needs live mode (a Gemini API key).")
    client = genai_client()
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=s.live_token_minutes)
    token = client.auth_tokens.create(
        config=types.CreateAuthTokenConfig(
            uses=1,
            expire_time=expires,
            new_session_expire_time=now + timedelta(minutes=2),
            live_connect_constraints=types.LiveConnectConstraints(
                model=s.model_live,
                config=types.LiveConnectConfig(
                    response_modalities=[types.Modality.AUDIO],
                    system_instruction=system_instruction,
                    input_audio_transcription=types.AudioTranscriptionConfig(),
                    output_audio_transcription=types.AudioTranscriptionConfig(),
                    temperature=0.4,
                ),
            ),
            lock_additional_fields=[],
            http_options=types.HttpOptions(api_version="v1alpha"),
        )
    )
    return {"token": token.name, "model": s.model_live, "expires_at": expires.isoformat(), "api_version": "v1alpha"}
