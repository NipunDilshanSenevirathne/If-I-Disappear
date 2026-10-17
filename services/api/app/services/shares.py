"""Handover links: the person staying gets their own page, on their own phone.

The person leaving picks who the link is for and which responsibilities it
covers. The link opens a read-only page with those responsibilities' card
entries and approved steps, and lets that one person practise them. It can't
see sources, other people's practice, the knowledge base or anything else, and
it can't change facts. The token is shown once; only its SHA-256 is stored, and
the person leaving can revoke it at any time.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid

from ..domain.household import Household
from ..store import HouseholdRecord
from ..store.base import ShareLink
from .card import build_card


class ShareError(ValueError):
    pass


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create(rec: HouseholdRecord, h: Household, person: str, responsibilities: list[str], actor: str) -> tuple[ShareLink, str]:
    ents = h.entity_map()
    if person not in ents or ents[person].kind != "person":
        raise ShareError("Choose who this link is for.")
    if ents[person].minor:
        raise ShareError("Handover links are for adults.")
    if person == h.settings.leaver:
        raise ShareError("Choose someone who is staying.")
    chosen = sorted({r for r in responsibilities if r in ents and ents[r].kind == "responsibility"})
    if not chosen:
        raise ShareError("Choose at least one responsibility to share.")
    if len([s for s in rec.shares if not s.revoked]) >= 10:
        raise ShareError("You have 10 active links. Revoke one you no longer need first.")
    token = secrets.token_urlsafe(24)
    link = ShareLink(id=f"s-{uuid.uuid4().hex[:8]}", token_hash=token_hash(token), person=person, responsibilities=chosen, created_by=actor)
    rec.shares.append(link)
    rec.share_hashes = [s.token_hash for s in rec.shares if not s.revoked]
    return link, token


def revoke(rec: HouseholdRecord, share_id: str) -> ShareLink:
    link = next((s for s in rec.shares if s.id == share_id), None)
    if link is None:
        raise ShareError("That link doesn't exist.")
    link.revoked = True
    rec.share_hashes = [s.token_hash for s in rec.shares if not s.revoked]
    return link


def find(rec: HouseholdRecord, token: str) -> ShareLink | None:
    th = token_hash(token)
    return next((s for s in rec.shares if s.token_hash == th and not s.revoked), None)


def listing(rec: HouseholdRecord, h: Household) -> list[dict]:
    ents = h.entity_map()
    return [
        {
            "id": s.id,
            "person": s.person,
            "person_name": ents[s.person].name if s.person in ents else s.person,
            "responsibilities": [{"id": r, "label": ents[r].name if r in ents else r} for r in s.responsibilities],
            "created": s.created.isoformat(),
            "revoked": s.revoked,
            "opened": s.opened,
        }
        for s in rec.shares
    ]


async def view(rec: HouseholdRecord, h: Household, link: ShareLink) -> dict:
    """Everything the person staying sees through their link, and nothing else."""
    ents = h.entity_map()
    card = await build_card(h, only=set(link.responsibilities))
    procs = {p.responsibility: p for p in h.procedures}
    practice = []
    for rid in link.responsibilities:
        p = procs.get(rid)
        if p is None or not p.approved:
            continue
        attempts = [a for a in h.practice_attempts if a.person == link.person and a.responsibility == rid]
        practice.append(
            {
                "responsibility": rid,
                "label": ents[rid].name if rid in ents else rid,
                "scenario": p.scenario_prompt,
                "steps": [{"id": s.id, "text": s.text, "critical": s.critical, "hint": s.hint} for s in p.steps],
                "attempts": [
                    {"id": a.id, "result": a.result, "created": a.created.isoformat() if a.created else None, "missed": a.missed}
                    for a in attempts[-5:]
                ],
            }
        )
    leaver = ents.get(h.settings.leaver)
    return {
        "household": h.settings.name,
        "person": link.person,
        "person_name": ents[link.person].name if link.person in ents else link.person,
        "leaver_name": leaver.name if leaver else "",
        "synthetic": h.settings.synthetic,
        "card": card,
        "practice": practice,
    }
