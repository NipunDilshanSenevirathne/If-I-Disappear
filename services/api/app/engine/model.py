"""The compiled household model the engine evaluates.

This is a typed, versioned *dependency and scheduling model*, not a causal
model: it evaluates whether recorded routes can satisfy responsibilities under
explicit assumptions. Every element keeps the claim ids it came from, so any
result can be explained with evidence.

The engine never calls a model, never touches the network and never writes
anything. It receives a World and a Scenario and returns results.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import date, time
from enum import Enum, IntEnum

from .tri import Tri

ENGINE_VERSION = "engine-1.0.0"
POLICY_VERSION = "readiness-v1"


# --------------------------------------------------------------------------- time


@dataclass(frozen=True)
class Window:
    """A time-of-day window on the day of an occurrence (local time)."""

    start: time
    end: time

    def overlaps(self, other: Window) -> bool:
        return self.start < other.end and other.start < self.end

    def label(self) -> str:
        return f"{self.start.strftime('%H:%M')}–{self.end.strftime('%H:%M')}"


class Freq(str, Enum):
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    ONGOING = "ongoing"


@dataclass(frozen=True)
class Recurrence:
    freq: Freq
    interval: int = 1
    weekdays: tuple[int, ...] = ()  # 0 = Monday
    monthday: int | None = None
    anchor: date | None = None  # dtstart for interval rules, the date for ONCE, month/day for YEARLY

    def label(self) -> str:
        names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        if self.freq is Freq.ONCE and self.anchor:
            return f"{self.anchor.day} {self.anchor.strftime('%b %Y')}"
        if self.freq is Freq.DAILY:
            return "every day" if self.interval == 1 else f"every {self.interval} days"
        if self.freq is Freq.MONTHLY and self.monthday:
            return f"every month on the {ordinal(self.monthday)}"
        if self.freq is Freq.WEEKLY:
            days = [names[d] for d in self.weekdays]
            joined = ", ".join(days[:-1]) + (" and " if len(days) > 1 else "") + days[-1] if days else "week"
            if self.interval == 1:
                return f"every {joined}"
            if self.interval == 2:
                return f"every second {joined}"
            return f"every {ordinal(self.interval)} {joined}"
        if self.freq is Freq.YEARLY and self.anchor:
            return f"every year on {self.anchor.day} {self.anchor.strftime('%b')}"
        return self.freq.value


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


# --------------------------------------------------------------------------- people


@dataclass
class Person:
    id: str
    name: str
    role: str = "household"  # leaver | backup | household | helper
    minor: bool = False
    claim_ids: tuple[str, ...] = ()


@dataclass
class Commitment:
    """A recurring time when a person is busy (e.g. airport runs)."""

    id: str
    person: str
    recurrence: Recurrence
    window: Window
    label: str
    movable: bool = True  # False: booked, paid or otherwise fixed; repairs never ask to move it
    claim_ids: tuple[str, ...] = ()


@dataclass
class Unavailability:
    """A dated period when a person is unavailable. Half-open [start, end)."""

    id: str
    person: str
    start: date
    end: date
    label: str
    claim_ids: tuple[str, ...] = ()


# --------------------------------------------------------------------------- resources


class ResourceKind(str, Enum):
    PHONE_NUMBER = "phone_number"
    HANDSET = "handset"
    CONTACT = "contact"
    DOCUMENT = "document"
    LOCATION = "location"
    ACCOUNT = "account"
    VEHICLE = "vehicle"
    PERMIT = "permit"
    SERVICE = "service"
    NOTE = "note"
    ITEM = "item"


@dataclass
class Resource:
    """Something a route needs.

    Access for a person is evaluated as:
      * holder logic: the holder, or people it is shared with, can use it; if the
        holder is away and it is not shared, others cannot; if the holder is present
        but has not shared it, the answer is unknown (they would need help);
      * stored_on: OR over containers (a contact saved on handset A *or* handset B);
      * requires: AND over prerequisites (a bank app needs the OTP phone number).
    Generic resources (a post-office counter, a note on the fridge) are available
    to every present adult, subject to stored_on/requires.
    """

    id: str
    kind: ResourceKind
    label: str
    holder: str | None = None
    shared_with: set[str] = field(default_factory=set)
    stored_on: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)
    generic: bool = False
    valid_until: date | None = None
    renewed_by: str | None = None
    identifier: str | None = None  # normalised identifier, e.g. a masked phone number
    claim_ids: tuple[str, ...] = ()


# --------------------------------------------------------------------------- responsibilities


class ReqKind(str, Enum):
    ACCESS = "access"  # the performer can reach a resource on the day
    VALID = "valid"  # a permit/document is valid on the day
    FACT = "fact"  # a stated condition holds (e.g. "driver accepts another time")


@dataclass(frozen=True)
class Requirement:
    kind: ReqKind
    target: str
    claim_ids: tuple[str, ...] = ()


@dataclass
class Route:
    """One complete way of achieving a responsibility (AND of its requirements).

    A responsibility is satisfied by any one complete route (OR over routes).
    Requirements of different routes are never mixed.
    """

    id: str
    responsibility: str
    label: str
    requirements: list[Requirement] = field(default_factory=list)
    performers: list[str] = field(default_factory=list)  # explicit route performers; empty = all candidates
    window: Window | None = None  # time needed on the day
    flexible_days: int = 0  # may be done on any of the N days before the due date
    weekdays: tuple[int, ...] | None = None  # allowed weekdays (e.g. offices Mon–Fri)
    requirements_known: bool = True
    alternate_day: bool = False  # this route moves the task to another agreed day
    claim_ids: tuple[str, ...] = ()


class Policy(str, Enum):
    LIGHT = "light"  # willing + has seen the instructions
    STANDARD = "standard"  # willing + explained it back without help
    CRITICAL = "critical"  # willing + explained without help + showed the key step


class Understanding(IntEnum):
    NONE = 0
    VIEWED = 1  # read or heard the instructions
    PRACTICED_WITH_HELP = 2  # explained with hints
    UNASSISTED = 3  # explained without hints (teach-back)


class Practical(IntEnum):
    NONE = 0
    SELF_REPORTED = 1  # says they did it
    WITNESSED = 2  # someone saw them do the key step


@dataclass
class HandoverRecord:
    """What has actually been shown about one person and one responsibility.

    Kept as separate fields on purpose: understanding, practical evidence and
    willingness are different things and are never collapsed into one level.
    """

    person: str
    responsibility: str
    understanding: Understanding = Understanding.NONE
    practical: Practical = Practical.NONE
    evidence_ids: tuple[str, ...] = ()


@dataclass
class Responsibility:
    id: str
    label: str
    category: str = "household"
    weight: int = 2  # 1 normal, 2 important, 3 health / income / legal (user-reviewed priority)
    recurrence: Recurrence = field(default_factory=lambda: Recurrence(Freq.ONGOING))
    lead_days: int = 0
    routes: list[Route] = field(default_factory=list)
    owners: list[str] = field(default_factory=list)  # people who already do it regularly
    policy: Policy = Policy.STANDARD
    awareness_required: bool = False
    awareness_sources: list[str] = field(default_factory=list)  # resources that tell you it is due (OR)
    demo_step: str | None = None  # the key step to show for CRITICAL policy
    in_scope: bool = True
    claim_ids: tuple[str, ...] = ()


# --------------------------------------------------------------------------- world


@dataclass
class Enabler:
    """A documented way to make a currently-false condition true, e.g. the school
    allows a second guardian number to be registered at the office."""

    label: str
    minutes: int = 30
    minutes_range: tuple[int, int] = (20, 60)
    owner_role: str = "leaver"  # who has to do it: leaver | backup
    evidence: str = "PROVIDER_CONFIRMATION"
    claim_ids: tuple[str, ...] = ()


@dataclass
class World:
    household_id: str
    version: int
    people: dict[str, Person] = field(default_factory=dict)
    resources: dict[str, Resource] = field(default_factory=dict)
    responsibilities: dict[str, Responsibility] = field(default_factory=dict)
    commitments: list[Commitment] = field(default_factory=list)
    unavailability: list[Unavailability] = field(default_factory=list)
    facts: dict[str, Tri] = field(default_factory=dict)
    fact_labels: dict[str, str] = field(default_factory=dict)
    fact_claims: dict[str, tuple[str, ...]] = field(default_factory=dict)
    willingness: dict[tuple[str, str], Tri] = field(default_factory=dict)  # (person, responsibility)
    willingness_claims: dict[tuple[str, str], tuple[str, ...]] = field(default_factory=dict)
    handovers: dict[tuple[str, str], HandoverRecord] = field(default_factory=dict)
    card_entries: set[str] = field(default_factory=set)  # responsibilities written on the Continuity Card
    commitment_exceptions: set[tuple[str, date]] = field(default_factory=set)  # (commitment id, date) agreed off
    fact_enablers: dict[str, Enabler] = field(default_factory=dict)  # how a false fact can be made true

    def copy(self) -> World:
        return copy.deepcopy(self)

    def handover(self, person: str, responsibility: str) -> HandoverRecord:
        return self.handovers.get((person, responsibility), HandoverRecord(person=person, responsibility=responsibility))

    def is_owner(self, person: str, responsibility: str) -> bool:
        resp = self.responsibilities.get(responsibility)
        return bool(resp and person in resp.owners)

    def candidates(self, resp: Responsibility, route: Route) -> list[str]:
        """People who could perform a route: explicit route performers, else anyone with a
        recorded willingness or ownership for the responsibility. Order is stable."""
        if route.performers:
            return list(route.performers)
        names: list[str] = []
        for person in resp.owners:
            if person not in names:
                names.append(person)
        for person, rid in sorted(self.willingness):
            if rid == resp.id and person not in names:
                names.append(person)
        return names


@dataclass
class Assumption:
    """A scenario assumption the household chose or confirmed.

    negotiable=False means the household has decided this (e.g. "I won't keep
    using this number"); repairs never propose undoing it on their own.
    """

    id: str
    kind: str  # "resource_unavailable" | "person_absent"
    target: str
    label: str
    negotiable: bool = False
    claim_ids: tuple[str, ...] = ()


@dataclass
class Scenario:
    """A dated absence. The window is half-open: [start, end)."""

    id: str
    leaver: str
    start: date
    end: date
    assumptions: list[Assumption] = field(default_factory=list)
    label: str = ""

    def person_absent(self, person: str, day: date) -> bool:
        if person == self.leaver and self.start <= day < self.end:
            return True
        for a in self.assumptions:
            if a.kind == "person_absent" and a.target == person and self.start <= day < self.end:
                return True
        return False

    def resource_unavailable(self, resource: str, day: date) -> Assumption | None:
        if not (self.start <= day < self.end):
            return None
        for a in self.assumptions:
            if a.kind == "resource_unavailable" and a.target == resource:
                return a
        return None

    def copy(self) -> Scenario:
        return copy.deepcopy(self)
