"""What the API returns for a household: everything the web app needs, nothing secret."""

from __future__ import annotations

from ..ai.quota import label
from ..ai.router import chain_for
from ..config import get_settings
from ..domain.household import Household
from ..store import HouseholdRecord
from .households import household_of, stages_for, variants_for
from .shares import listing


def household_view(rec: HouseholdRecord, h: Household | None = None) -> dict:
    h = h or household_of(rec)
    s = get_settings()
    ents = h.entity_map()
    people = [{"id": e.id, "name": e.name, "role": e.role, "minor": e.minor} for e in h.entities if e.kind == "person"]
    sources = []
    for src in h.sources:
        claims_from = [c.id for c in h.claims if src.id in c.source_ids or any(ev.source_id == src.id for ev in c.evidence)]
        sources.append(
            {
                **src.model_dump(mode="json", exclude={"file"}),
                "has_file": bool(src.file),
                "speaker_name": ents[src.speaker].name if src.speaker in ents else None,
                "claim_count": len(claims_from),
            }
        )
    return {
        "id": rec.id,
        "name": h.settings.name,
        "demo": rec.demo,
        "demo_source": rec.demo_source,
        "variant": h.variant,
        "variants": variants_for(rec),
        "stages_available": stages_for(rec),
        "stages_applied": h.stages_applied,
        "version": h.version,
        "rev": rec.rev,
        "settings": h.settings.model_dump(mode="json"),
        "people": people,
        "entities": [e.model_dump(mode="json") for e in h.entities],
        "sources": sources,
        "claims": [c.model_dump(mode="json") for c in h.claims],
        "procedures": [p.model_dump(mode="json") for p in h.procedures],
        "attempts": [a.model_dump(mode="json") for a in h.practice_attempts],
        "events": [e.model_dump(mode="json") for e in h.handover_events],
        "analysis": rec.analysis,
        "ai": {
            "mode": s.ai_mode,
            "live_voice": s.live,
            "tier": s.quota_tier,
            "models": {
                "extract": label(chain_for("extractor")[0].model),
                "review": label(chain_for("challenger")[0].model),
                "live": label(s.model_live),
            }
            if s.live
            else None,
        },
        "history": [p.model_dump(mode="json") for p in rec.history],
        "shares": listing(rec, h),
        "log": [entry.model_dump(mode="json") for entry in rec.log[-60:]],
        "updated": rec.updated.isoformat(),
    }
