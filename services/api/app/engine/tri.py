"""Three-valued logic used by the deterministic engine.

T = supported and satisfied under the scenario.
F = supported evidence shows it is unavailable or incompatible at the required time.
U = unknown, disputed, stale or insufficiently specified.

The rules follow the specification:
  * conjunction (all requirements of one route): any F -> F, otherwise any U -> U, otherwise T
  * alternatives (several complete routes):     any T -> T, otherwise any U -> U, otherwise F
An empty list of alternatives is U ("no way of doing this is recorded"), never success.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import Enum


class Tri(str, Enum):
    T = "T"
    F = "F"
    U = "U"

    @property
    def word(self) -> str:
        return {"T": "works", "F": "blocked", "U": "unknown"}[self.value]


def t_and(values: Iterable[Tri]) -> Tri:
    """Conjunction. An empty conjunction is T: callers must decide separately
    whether an empty requirement list is acceptable (see Route.requirements_known)."""
    has_unknown = False
    for value in values:
        if value is Tri.F:
            return Tri.F
        if value is Tri.U:
            has_unknown = True
    return Tri.U if has_unknown else Tri.T


def t_or(values: Iterable[Tri]) -> Tri:
    """Alternatives. An empty set of alternatives is U, never T or F."""
    seen = False
    has_unknown = False
    for value in values:
        seen = True
        if value is Tri.T:
            return Tri.T
        if value is Tri.U:
            has_unknown = True
    if not seen:
        return Tri.U
    return Tri.U if has_unknown else Tri.F


def worst(values: Iterable[Tri]) -> Tri:
    """Aggregate over dated occurrences: one blocked date blocks the responsibility."""
    return t_and(values)
