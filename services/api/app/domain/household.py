"""A household's full knowledge base, and loading the synthetic demo households.

A Household bundles everything the engine and the UI need: settings, entities,
sources, claims (with review state), procedures, handover events and practice
attempts. It is plain data; `compile()` turns accepted claims into the engine's
World and Scenario.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .claims import Claim, Entity, HandoverEvent, HouseholdSettings, PracticeAttempt, Procedure, Source
from .compile import Compiled, compile_household

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "households"


@dataclass
class Variant:
    id: str
    title: str
    summary: str
    remove_claims: list[str] = field(default_factory=list)
    add_claims: list[Claim] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass
class Stage:
    id: str
    title: str
    date: date | None
    sources: list[Source]
    claims: list[Claim]
    supersede: list[str]
    card_entries: list[str]
    handover_events: list[HandoverEvent]
    practice_attempts: list[PracticeAttempt]


@dataclass
class Household:
    settings: HouseholdSettings
    entities: list[Entity]
    sources: list[Source]
    claims: list[Claim]
    procedures: list[Procedure] = field(default_factory=list)
    handover_events: list[HandoverEvent] = field(default_factory=list)
    practice_attempts: list[PracticeAttempt] = field(default_factory=list)
    stages_applied: list[str] = field(default_factory=list)
    variant: str | None = None
    version: int = 1

    # ------------------------------------------------------------------ lookups
    def source_map(self) -> dict[str, Source]:
        return {s.id: s for s in self.sources}

    def entity_map(self) -> dict[str, Entity]:
        return {e.id: e for e in self.entities}

    def claim(self, cid: str) -> Claim | None:
        return next((c for c in self.claims if c.id == cid), None)

    # ------------------------------------------------------------------ compile
    def compile(self) -> Compiled:
        return compile_household(
            self.settings,
            self.entities,
            self.claims,
            handover_events=self.handover_events,
            procedures=self.procedures,
            world_version=self.version,
        )

    def copy(self) -> Household:
        return Household(
            settings=self.settings.model_copy(deep=True),
            entities=[e.model_copy(deep=True) for e in self.entities],
            sources=[s.model_copy(deep=True) for s in self.sources],
            claims=[c.model_copy(deep=True) for c in self.claims],
            procedures=[p.model_copy(deep=True) for p in self.procedures],
            handover_events=[h.model_copy(deep=True) for h in self.handover_events],
            practice_attempts=[a.model_copy(deep=True) for a in self.practice_attempts],
            stages_applied=list(self.stages_applied),
            variant=self.variant,
            version=self.version,
        )


# ---------------------------------------------------------------------- loading


def _read(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _claims(raw: list[dict], defaults: dict | None = None) -> list[Claim]:
    out = []
    for item in raw or []:
        data = dict(defaults or {})
        data.update(item)
        out.append(Claim.model_validate(data))
    return out


def household_dir(household_id: str) -> Path:
    path = FIXTURES / household_id
    if not path.is_dir():
        raise FileNotFoundError(f"No fixture household '{household_id}' in {FIXTURES}")
    return path


def available_households() -> list[str]:
    return sorted(p.name for p in FIXTURES.iterdir() if (p / "household.yaml").exists())


def load_household(household_id: str = "perera") -> Household:
    base = household_dir(household_id)
    hh = _read(base / "household.yaml")
    src = _read(base / "sources.yaml")
    cl = _read(base / "claims.yaml")
    defaults = {"review": "accepted", "created_by": "fixture"}
    defaults.update(cl.get("defaults") or {})
    return Household(
        settings=HouseholdSettings.model_validate(hh["settings"]),
        entities=[Entity.model_validate(e) for e in hh.get("entities", [])],
        sources=[Source.model_validate(s) for s in src.get("sources", [])],
        claims=_claims(cl.get("claims", []), defaults),
        procedures=[Procedure.model_validate(p) for p in hh.get("procedures", [])],
    )


def load_stage(household_id: str = "perera", name: str = "evidence") -> Stage | None:
    path = household_dir(household_id) / f"{name}.yaml"
    if not path.exists():
        return None
    raw = _read(path)
    defaults = {"review": "accepted", "created_by": "evidence"}
    return Stage(
        id=raw.get("stage", name),
        title=raw.get("title", name),
        date=raw.get("date"),
        sources=[Source.model_validate(s) for s in raw.get("sources", [])],
        claims=_claims(raw.get("claims", []), defaults),
        supersede=list(raw.get("supersede", [])),
        card_entries=list(raw.get("card_entries", [])),
        handover_events=[HandoverEvent.model_validate(h) for h in raw.get("handover_events", [])],
        practice_attempts=[PracticeAttempt.model_validate(a) for a in raw.get("practice_attempts", [])],
    )


def load_variants(household_id: str = "perera") -> list[Variant]:
    path = household_dir(household_id) / "variants.yaml"
    if not path.exists():
        return []
    raw = _read(path)
    out = []
    for v in raw.get("variants", []):
        out.append(
            Variant(
                id=v["id"],
                title=v["title"],
                summary=v.get("summary", ""),
                remove_claims=list(v.get("remove_claims", [])),
                add_claims=_claims(v.get("add_claims", []), {"review": "accepted", "created_by": "household"}),
                settings=dict(v.get("settings") or {}),
            )
        )
    return out


def demo_index() -> list[dict]:
    """The households a visitor can open, with what the picker shows about each."""
    path = FIXTURES / "demos.yaml"
    listed = (_read(path).get("demos") if path.exists() else None) or [{"id": h} for h in available_households()]
    out = []
    for item in listed:
        hid = item["id"]
        try:
            h = load_household(hid)
        except FileNotFoundError:
            continue
        people = {e.id: e for e in h.entities if e.kind == "person"}
        s = h.settings
        out.append(
            {
                "id": hid,
                "name": s.name,
                "story": item.get("story", ""),
                "kind": item.get("kind", "migration"),
                "leaver": people[s.leaver].name if s.leaver in people else s.leaver,
                "at_home": [p.name for pid, p in people.items() if pid != s.leaver],
                "destination": s.destination,
                "absence": s.absence,
                "airport_from": s.airport_from,
                "airport_to": s.airport_to,
                "departure": s.departure.isoformat(),
                "horizon_days": s.horizon_days,
                "languages": list(s.languages),
                "responsibilities": sum(1 for e in h.entities if e.kind == "responsibility"),
                "sources": len(h.sources),
                "later_stage": (household_dir(hid) / "evidence.yaml").exists(),
                "variants": len(load_variants(hid)),
            }
        )
    return out


def load_gold(household_id: str = "perera") -> dict:
    path = household_dir(household_id) / "gold.yaml"
    return _read(path) if path.exists() else {}


# ---------------------------------------------------------------------- changing a household


def apply_stage(h: Household, stage: Stage) -> Household:
    out = h.copy()
    known = {s.id for s in out.sources}
    out.sources += [s for s in stage.sources if s.id not in known]
    for c in out.claims:
        if c.id in stage.supersede:
            c.review = "superseded"
    existing = {c.id for c in out.claims}
    out.claims += [c for c in stage.claims if c.id not in existing]
    cards = list(dict.fromkeys(list(out.settings.card_entries) + stage.card_entries))
    out.settings = out.settings.model_copy(update={"card_entries": cards})
    out.handover_events += stage.handover_events
    out.practice_attempts += stage.practice_attempts
    out.stages_applied.append(stage.id)
    out.version += 1
    return out


def apply_variant(h: Household, variant: Variant) -> Household:
    out = h.copy()
    for c in out.claims:
        if c.id in variant.remove_claims:
            c.review = "withdrawn"
    out.claims += [c.model_copy(deep=True) for c in variant.add_claims]
    if variant.settings:
        out.settings = out.settings.model_copy(update=variant.settings)
        if "departure" in variant.settings and isinstance(variant.settings["departure"], str):
            out.settings = out.settings.model_copy(update={"departure": date.fromisoformat(variant.settings["departure"])})
    out.variant = variant.id
    out.version += 1
    return out


def demo_household(household_id: str = "perera", stage: str = "capture", variant: str | None = None) -> Household:
    """The demo household at a named stage ('capture' or 'after_handover'), optionally with a variant."""
    h = load_household(household_id)
    if stage != "capture":
        st = load_stage(household_id)
        if st is None:
            raise ValueError(f"Household '{household_id}' has no evidence stage")
        h = apply_stage(h, st)
    if variant:
        v = next((x for x in load_variants(household_id) if x.id == variant), None)
        if v is None:
            raise ValueError(f"Unknown variant '{variant}'")
        h = apply_variant(h, v)
    return h


__all__ = [
    "FIXTURES",
    "Household",
    "Stage",
    "Variant",
    "apply_stage",
    "apply_variant",
    "available_households",
    "demo_household",
    "demo_index",
    "load_gold",
    "load_household",
    "load_stage",
    "load_variants",
    "replace",
]


# ---------------------------------------------------------------------- persistence


def household_to_dict(h: Household) -> dict:
    return {
        "settings": h.settings.model_dump(mode="json"),
        "entities": [e.model_dump(mode="json") for e in h.entities],
        "sources": [s.model_dump(mode="json") for s in h.sources],
        "claims": [c.model_dump(mode="json") for c in h.claims],
        "procedures": [p.model_dump(mode="json") for p in h.procedures],
        "handover_events": [e.model_dump(mode="json") for e in h.handover_events],
        "practice_attempts": [a.model_dump(mode="json") for a in h.practice_attempts],
        "stages_applied": list(h.stages_applied),
        "variant": h.variant,
        "version": h.version,
    }


def household_from_dict(d: dict) -> Household:
    return Household(
        settings=HouseholdSettings.model_validate(d["settings"]),
        entities=[Entity.model_validate(e) for e in d.get("entities", [])],
        sources=[Source.model_validate(s) for s in d.get("sources", [])],
        claims=[Claim.model_validate(c) for c in d.get("claims", [])],
        procedures=[Procedure.model_validate(p) for p in d.get("procedures", [])],
        handover_events=[HandoverEvent.model_validate(e) for e in d.get("handover_events", [])],
        practice_attempts=[PracticeAttempt.model_validate(a) for a in d.get("practice_attempts", [])],
        stages_applied=list(d.get("stages_applied", [])),
        variant=d.get("variant"),
        version=int(d.get("version", 1)),
    )
