"""Typed effects: the only way a plan step or accepted evidence changes the model.

Plan steps carry effects so the optimiser can ask "what if this were done?" on a
copy of the world. Accepted evidence uses exactly the same effects, applied to
the household's committed world. A plan never changes the current state by
itself; only accepted evidence does.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .model import HandoverRecord, Practical, Scenario, Understanding, World
from .tri import Tri


@dataclass(frozen=True)
class Effect:
    kind: str
    person: str | None = None
    responsibility: str | None = None
    resource: str | None = None
    container: str | None = None
    fact: str | None = None
    assumption: str | None = None
    commitment: str | None = None
    day: date | None = None
    level: int | None = None
    new_date: date | None = None

    def describe(self) -> str:
        return f"{self.kind}({', '.join(f'{k}={v}' for k, v in self.__dict__.items() if v is not None and k != 'kind')})"


# Effect kinds
WILLING = "willing"  # person agrees to a responsibility
SHARE = "share"  # resource shared with person
STORE_ON = "store_on"  # e.g. a contact saved on another handset
FACT_TRUE = "fact_true"  # a condition confirmed
UNDERSTANDING = "understanding"  # level reached for (person, responsibility)
PRACTICAL = "practical"  # practical evidence level for (person, responsibility)
CARD = "card"  # responsibility written on the Continuity Card (dates known)
VALID_UNTIL = "valid_until"  # permit renewed with a new validity date
DROP_ASSUMPTION = "drop_assumption"  # household changes a negotiable assumption
COMMITMENT_OFF = "commitment_off"  # person agrees to be free on one date


@dataclass
class Applied:
    world: World
    scenario: Scenario
    notes: list[str] = field(default_factory=list)


def apply_effects(world: World, scenario: Scenario, effects: list[Effect], *, in_place: bool = False) -> Applied:
    w = world if in_place else world.copy()
    s = scenario if in_place else scenario.copy()
    notes: list[str] = []
    for e in effects:
        if e.kind == WILLING and e.person and e.responsibility:
            w.willingness[(e.person, e.responsibility)] = Tri.T
        elif e.kind == SHARE and e.resource in w.resources and e.person:
            w.resources[e.resource].shared_with.add(e.person)
        elif e.kind == STORE_ON and e.resource in w.resources and e.container:
            stored = w.resources[e.resource].stored_on
            if e.container not in stored:
                stored.append(e.container)
        elif e.kind == FACT_TRUE and e.fact:
            w.facts[e.fact] = Tri.T
        elif e.kind == UNDERSTANDING and e.person and e.responsibility and e.level is not None:
            rec = w.handovers.get((e.person, e.responsibility), HandoverRecord(e.person, e.responsibility))
            rec.understanding = Understanding(max(int(rec.understanding), int(e.level)))
            w.handovers[(e.person, e.responsibility)] = rec
        elif e.kind == PRACTICAL and e.person and e.responsibility and e.level is not None:
            rec = w.handovers.get((e.person, e.responsibility), HandoverRecord(e.person, e.responsibility))
            rec.practical = Practical(max(int(rec.practical), int(e.level)))
            w.handovers[(e.person, e.responsibility)] = rec
        elif e.kind == CARD and e.responsibility:
            w.card_entries.add(e.responsibility)
        elif e.kind == VALID_UNTIL and e.resource in w.resources and e.new_date:
            res = w.resources[e.resource]
            if res.valid_until is None or e.new_date > res.valid_until:
                res.valid_until = e.new_date
                # a renewal tied to this permit is now due at the new expiry
                if res.renewed_by and res.renewed_by in w.responsibilities:
                    from .model import Freq, Recurrence

                    resp = w.responsibilities[res.renewed_by]
                    if resp.recurrence.freq is Freq.ONCE:
                        resp.recurrence = Recurrence(Freq.ONCE, anchor=e.new_date)
        elif e.kind == DROP_ASSUMPTION and e.assumption:
            s.assumptions = [a for a in s.assumptions if a.id != e.assumption]
        elif e.kind == COMMITMENT_OFF and e.commitment and e.day:
            w.commitment_exceptions.add((e.commitment, e.day))
        else:
            notes.append(f"ignored effect {e.describe()}")
    return Applied(w, s, notes)
