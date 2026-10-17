"""Ingest one source: listen or read it, extract claims, verify every quote, resolve entities.

ADK graph:

    START -> route_source --listen--> listener (agent) -> after_listen --+
                          --read----> reader (agent)   -> after_read  ---+--> extractor (agent) -> verify_and_resolve
                          --text----> text_ready ------------------------+

Code decides what is kept: quotes must match the stored text exactly, entities
are matched to known ones before new ones are proposed, secrets are rejected,
and nothing is accepted without the household's review.
"""

from __future__ import annotations

import re
from datetime import date

from google.adk import Agent, Event, Workflow
from google.genai import types

from ..ai import fixture
from ..ai.context import extraction_prompt, media_instruction
from ..ai.llm import generation_config, model_for, prompt
from ..ai.redact import redact
from ..ai.schemas import Extraction, ProposedClaim, ProposedEntity, Reading, Transcript
from ..config import get_settings
from ..domain.claims import Claim, Entity, EvidenceRef, ScheduleSpec, Source, WindowSpec
from ..domain.compile import normalise_identifier
from ..domain.household import Household
from ..verify.quotes import check_claim, normalise, with_locators
from .runner import run_workflow

REQUIRED: dict[str, tuple[str, ...]] = {
    "DOES": ("object",),
    "CAN_DO": ("object", "value"),
    "IMPORTANCE": ("value",),
    "SCHEDULE": ("schedule",),
    "LEAD_TIME": ("value",),
    "KEY_STEP": ("value",),
    "HANDOVER_LEVEL": ("value",),
    "AMOUNT": ("value",),
    "ROUTE": ("object",),
    "ROUTE_NEEDS": ("object",),
    "ROUTE_NEEDS_VALID": ("object",),
    "ROUTE_NEEDS_FACT": ("object",),
    "ROUTE_PERFORMER": ("object",),
    "ROUTE_WINDOW": ("window",),
    "ROUTE_FLEXIBLE": ("value",),
    "ROUTE_WEEKDAYS": ("value",),
    "NEEDS": ("object",),
    "NEEDS_VALID": ("object",),
    "HOLDS": ("object",),
    "STORED_ON": ("object",),
    "SHARED_WITH": ("object",),
    "REQUIRES_RESOURCE": ("object",),
    "NOTIFIES": ("object",),
    "MENTIONED_ON": ("object",),
    "VALID_UNTIL": ("date",),
    "RENEWS": ("object",),
    "STOPS_DURING_ABSENCE": ("value",),
    "BUSY": ("window",),
    "UNAVAILABLE": ("date",),
    "FREE_ON": ("date", "value"),
    "FACT": ("value",),
    "ENABLES": ("value",),
    "KNOWS_SECRET": ("object",),
}


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s or "item"


def _date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value[:10])


ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def tidy(pc: ProposedClaim) -> ProposedClaim:
    """Put a value the model wrote in the wrong field where it belongs, when the right field
    is empty and the predicate has no use for the other one (a date in `object` for
    VALID_UNTIL, a number in `object` for LEAD_TIME). Nothing else changes: the claim is
    still quote-checked and still waits for a person to accept it."""
    need = REQUIRED.get(pc.predicate, ())
    update: dict = {}
    if "date" in need and not pc.date:
        if pc.object and ISO_DATE.fullmatch(pc.object.strip()):
            update = {"date": pc.object.strip(), "object": None}
        elif "value" not in need and pc.value and ISO_DATE.fullmatch(pc.value.strip()):
            update = {"date": pc.value.strip(), "value": None}
    elif "value" in need and "object" not in need and not pc.value and pc.object:
        update = {"value": pc.object, "object": None}
    return pc.model_copy(update=update) if update else pc


class IngestContext:
    def __init__(
        self,
        household: Household,
        source: Source,
        data: bytes | None = None,
        mime_type: str | None = None,
        fixture_id: str | None = None,
    ):
        self.h = household
        self.source = source
        self.data = data
        self.mime_type = mime_type or source.mime_type
        self.replay: tuple[str, str] | None = None
        self.result: dict = {}
        if data is not None:
            self.replay = fixture.recognise(data)
        elif fixture_id and fixture.fixture_source(fixture_id, source.id) is not None:
            self.replay = (fixture_id, source.id)

    # ------------------------------------------------------------------ routing
    def route(self) -> str:
        if self.data is not None and self.source.kind == "voice":
            return "listen"
        if self.data is not None and self.source.kind in ("image", "pdf"):
            return "read"
        return "text"

    def media_content(self, task: str) -> types.Content:
        return types.Content(
            role="user",
            parts=[
                types.Part(text=media_instruction(self.source, task)),
                types.Part(inline_data=types.Blob(mime_type=self.mime_type, data=self.data)),
            ],
        )

    # ------------------------------------------------------------------ results of listening / reading
    def apply_transcript(self, t: Transcript) -> None:
        red = redact(t.text)
        self.source.text = red.text
        self.source.text_original = None
        self.source.language = "en"
        self.source.redactions = max(t.secrets_removed, red.secrets_removed)

    def apply_reading(self, r: Reading) -> None:
        red = redact(r.text)
        self.source.text = red.text
        self.source.language = "en"
        self.source.redactions = max(r.secrets_removed, red.secrets_removed)
        self.source.synthetic = r.is_sample

    def apply_text(self) -> None:
        red = redact(self.source.text)
        self.source.text = red.text
        self.source.redactions = max(self.source.redactions, red.secrets_removed)

    def extraction_prompt(self) -> str:
        return extraction_prompt(self.h, self.source)

    # ------------------------------------------------------------------ fixture responders
    def replay_listen(self, text, media) -> Transcript:
        if self.replay:
            return fixture.replay_transcript(*self.replay)
        return Transcript(text="")

    def replay_read(self, text, media) -> Reading:
        if self.replay:
            return fixture.replay_reading(*self.replay)
        return Reading(kind="other", text="")

    def replay_extract(self, text, media) -> Extraction:
        if self.replay and normalise(self.source.text) == normalise(fixture.fixture_source(*self.replay).text):
            known = {e.id for e in self.h.entities}
            return fixture.replay_extraction(self.replay[0], self.replay[1], known)
        return Extraction(source_summary=fixture.OFFLINE_NOTE, questions=[fixture.OFFLINE_NOTE])

    # ------------------------------------------------------------------ verify and resolve
    def resolve_entity(self, pe: ProposedEntity) -> str:
        ents = self.h.entity_map()
        if pe.ref in ents:
            return pe.ref
        key = normalise(pe.name).lower()
        for e in self.h.entities:
            names = [normalise(e.name).lower()] + [normalise(a).lower() for a in e.aliases]
            if e.kind == pe.kind and key in names:
                return e.id
        if pe.identifier:
            ident = normalise_identifier(pe.identifier)
            for e in self.h.entities:
                if e.identifier and normalise_identifier(e.identifier) == ident:
                    return e.id
        base = slug(pe.ref.removeprefix("new:"))
        new_id, n = base, 2
        while new_id in ents:
            new_id, n = f"{base}_{n}", n + 1
        self.h.entities.append(
            Entity(
                id=new_id,
                kind=pe.kind,
                name=redact(pe.name).text,
                resource_kind=pe.resource_kind if pe.kind == "resource" else None,
                identifier=redact(pe.identifier).text if pe.identifier else None,
                minor=pe.minor,
                role="household" if pe.kind == "person" else None,
                proposed=True,
            )
        )
        return new_id

    def to_claim(self, pc: ProposedClaim, refs: dict[str, str], index: int) -> Claim:
        pc = tidy(pc)
        issues: list[str] = []
        known = self.h.entity_map()

        def map_ref(x: str | None) -> str | None:
            if x is None:
                return None
            y = refs.get(x, x)
            if y not in known and y not in refs.values():
                issues.append(f"'{x}' isn't a known person, task or thing.")
            return y

        schedule = window = None
        claim_date = end_date = None
        try:
            claim_date, end_date = _date(pc.date), _date(pc.end_date)
            if pc.schedule:
                schedule = ScheduleSpec(
                    freq=pc.schedule.freq,
                    interval=max(1, pc.schedule.interval),
                    weekdays=list(pc.schedule.weekdays),
                    monthday=pc.schedule.monthday,
                    anchor=_date(pc.schedule.anchor),
                )
            if pc.window:
                for t in (pc.window.start, pc.window.end):
                    if not re.fullmatch(r"\d{1,2}:\d{2}", t):
                        raise ValueError(f"bad time {t}")
                window = WindowSpec(start=pc.window.start, end=pc.window.end)
        except ValueError as exc:
            issues.append(f"A date or time couldn't be read ({exc}).")
        value = pc.value
        if value and redact(value).secrets_removed:
            issues.append("This looked like a secret, so it was removed.")
            value = "[secret removed]"
        claim = Claim(
            id=f"{self.source.id}-{index:02d}",
            predicate=pc.predicate,
            subject=map_ref(pc.subject) or pc.subject,
            object=map_ref(pc.object),
            value=value,
            date=claim_date,
            end_date=end_date,
            schedule=schedule,
            window=window,
            fixed=pc.fixed,
            evidence=[EvidenceRef(source_id=self.source.id, quote=q) for q in pc.quotes if q.strip()],
            derivation=pc.derivation,
            note=redact(pc.note).text if pc.note else None,
            confidence=pc.confidence,
            review="unreviewed",
            created_by="extractor",
            source_ids=[self.source.id],
            stated_by=self.source.speaker if pc.derivation == "user_statement" else None,
        )
        for field_name in REQUIRED.get(pc.predicate, ()):
            if getattr(claim, field_name) in (None, "", []):
                issues.append(f"Missing {field_name} for {pc.predicate}.")
        return claim.model_copy(update={"issues": issues})

    @staticmethod
    def _key(c: Claim) -> tuple:
        return (
            c.predicate,
            c.subject,
            c.object,
            (c.value or "").strip().lower(),
            c.date,
            c.schedule.model_dump_json() if c.schedule else None,
            c.window.model_dump_json() if c.window else None,
        )

    def apply_extraction(self, ex: Extraction) -> dict:
        refs = {pe.ref: self.resolve_entity(pe) for pe in ex.entities}
        sources = self.h.source_map()
        sources[self.source.id] = self.source
        existing = {self._key(c): c for c in self.h.claims if c.review not in ("withdrawn", "superseded")}
        added = merged = unsupported = 0
        new_ids: list[str] = []
        for i, pc in enumerate(ex.claims, start=1):
            claim = self.to_claim(pc, refs, i)
            check = check_claim(claim, sources)
            claim = with_locators(claim, sources)
            issues = list(claim.issues) + check.issues
            claim = claim.model_copy(update={"verified": check.supported and not claim.issues, "issues": issues})
            if not claim.verified:
                unsupported += 1
            dup = existing.get(self._key(claim))
            if dup is not None and claim.verified:
                have = {(e.source_id, e.quote) for e in dup.evidence}
                dup.evidence += [e for e in claim.evidence if (e.source_id, e.quote) not in have]
                if self.source.id not in dup.source_ids:
                    dup.source_ids.append(self.source.id)
                merged += 1
                continue
            self.h.claims.append(claim)
            existing[self._key(claim)] = claim
            new_ids.append(claim.id)
            added += 1
        self.source.summary = ex.source_summary
        self.source.status = "ready"
        self.result = {
            "source_id": self.source.id,
            "added": added,
            "merged": merged,
            "unsupported": unsupported,
            "new_claims": new_ids,
            "questions": ex.questions,
            "summary": ex.source_summary,
            "replayed": bool(self.replay) and not get_settings().live,
        }
        return self.result


def build_ingest(ctx: IngestContext) -> Workflow:
    cfg = generation_config(0.0)
    listener = Agent(
        name="listener",
        model=model_for("listener", ctx.replay_listen),
        instruction=prompt("listener"),
        output_schema=Transcript,
        generate_content_config=cfg,
    )
    reader = Agent(
        name="reader",
        model=model_for("reader", ctx.replay_read),
        instruction=prompt("reader"),
        output_schema=Reading,
        generate_content_config=cfg,
    )
    extractor = Agent(
        name="extractor",
        model=model_for("extractor", ctx.replay_extract),
        instruction=prompt("extractor"),
        output_schema=Extraction,
        generate_content_config=generation_config(0.1, thinking="low"),
    )

    def route_source(node_input):
        r = ctx.route()
        if r == "listen":
            return Event(route=["listen"], output=ctx.media_content("listen"))
        if r == "read":
            return Event(route=["read"], output=ctx.media_content("read"))
        return Event(route=["text"], output=ctx.source.id)

    def after_listen(node_input: Transcript):
        ctx.apply_transcript(node_input)
        if not ctx.source.text.strip():
            raise ValueError(fixture.OFFLINE_NOTE)
        return ctx.extraction_prompt()

    def after_read(node_input: Reading):
        ctx.apply_reading(node_input)
        if not ctx.source.text.strip():
            raise ValueError(fixture.OFFLINE_NOTE)
        return ctx.extraction_prompt()

    def text_ready(node_input):
        ctx.apply_text()
        return ctx.extraction_prompt()

    def verify_and_resolve(node_input: Extraction):
        return ctx.apply_extraction(node_input)

    return Workflow(
        name="ingest",
        edges=[
            ("START", route_source),
            (route_source, {"listen": listener, "read": reader, "text": text_ready}),
            (listener, after_listen, extractor),
            (reader, after_read, extractor),
            (text_ready, extractor),
            (extractor, verify_and_resolve),
        ],
    )


async def ingest_source(ctx: IngestContext, trace: list[dict]) -> dict:
    await run_workflow(build_ingest(ctx), ctx.source.id, trace)
    if not ctx.result:
        raise RuntimeError("The extraction didn't finish.")
    return ctx.result
