"""Tiny builders for hand-made worlds used by the unit tests."""

from __future__ import annotations

from datetime import date, time

from app.engine.model import (
    Commitment,
    Freq,
    Person,
    Policy,
    Recurrence,
    ReqKind,
    Requirement,
    Resource,
    ResourceKind,
    Responsibility,
    Route,
    Scenario,
    Window,
    World,
)

START = date(2026, 11, 1)  # a Sunday
END = date(2026, 12, 1)


def world(*people: Person) -> World:
    w = World(household_id="test", version=1)
    for p in people:
        w.people[p.id] = p
    return w


def people() -> list[Person]:
    return [
        Person("amma", "Amma", role="leaver"),
        Person("appa", "Appa", role="backup"),
        Person("aunty", "Aunty", role="helper"),
        Person("kid", "Kid", minor=True),
    ]


def scenario(**kw) -> Scenario:
    return Scenario(id="s", leaver="amma", start=kw.get("start", START), end=kw.get("end", END), assumptions=kw.get("assumptions", []))


def res(rid: str, kind: ResourceKind = ResourceKind.DOCUMENT, **kw) -> Resource:
    return Resource(id=rid, kind=kind, label=kw.pop("label", rid), **kw)


def access(target: str) -> Requirement:
    return Requirement(ReqKind.ACCESS, target)


def valid(target: str) -> Requirement:
    return Requirement(ReqKind.VALID, target)


def fact(target: str) -> Requirement:
    return Requirement(ReqKind.FACT, target)


def route(rid: str, resp: str, *reqs: Requirement, **kw) -> Route:
    return Route(id=rid, responsibility=resp, label=kw.pop("label", rid), requirements=list(reqs), **kw)


def resp(rid: str, *routes: Route, **kw) -> Responsibility:
    kw.setdefault("recurrence", Recurrence(Freq.ONGOING))
    kw.setdefault("policy", Policy.LIGHT)
    return Responsibility(id=rid, label=kw.pop("label", rid), routes=list(routes), **kw)


def weekly(*weekdays: int, anchor: date | None = None) -> Recurrence:
    return Recurrence(Freq.WEEKLY, weekdays=tuple(weekdays), anchor=anchor)


def once(d: date) -> Recurrence:
    return Recurrence(Freq.ONCE, anchor=d)


def win(a: str, b: str) -> Window:
    h1, m1 = map(int, a.split(":"))
    h2, m2 = map(int, b.split(":"))
    return Window(time(h1, m1), time(h2, m2))


def busy(cid: str, person: str, rec: Recurrence, a: str, b: str, label: str = "work", movable: bool = True) -> Commitment:
    return Commitment(id=cid, person=person, recurrence=rec, window=win(a, b), label=label, movable=movable)
