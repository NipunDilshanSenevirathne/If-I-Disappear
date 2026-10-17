"""Dates, recurrences and windows.

All engine dates are local calendar dates of the household's timezone. Scenario
windows are half-open: [start, end). An occurrence on `end` is excluded.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from dateutil.rrule import DAILY, WEEKLY, YEARLY, rrule

from .model import Commitment, Freq, Recurrence, Responsibility, Scenario, World

_WEEKDAY_CONSTS = None


def _weekday_consts():
    global _WEEKDAY_CONSTS
    if _WEEKDAY_CONSTS is None:
        from dateutil.rrule import FR, MO, SA, SU, TH, TU, WE

        _WEEKDAY_CONSTS = (MO, TU, WE, TH, FR, SA, SU)
    return _WEEKDAY_CONSTS


def expand(rec: Recurrence, start: date, end: date) -> list[date]:
    """Dates of a recurrence inside [start, end). ONGOING returns []: ongoing
    responsibilities are evaluated on check dates instead (see check_dates)."""
    if end <= start:
        return []
    if rec.freq is Freq.ONGOING:
        return []
    if rec.freq is Freq.ONCE:
        return [rec.anchor] if rec.anchor and start <= rec.anchor < end else []

    last = end - timedelta(days=1)
    kwargs: dict = {"interval": max(1, rec.interval), "until": _dt(last)}
    if rec.freq is Freq.DAILY:
        rule = rrule(DAILY, dtstart=_dt(start), **kwargs)
    elif rec.freq is Freq.WEEKLY:
        days = rec.weekdays or ((rec.anchor or start).weekday(),)
        anchor = rec.anchor or start
        consts = _weekday_consts()
        rule = rrule(WEEKLY, dtstart=_dt(anchor), byweekday=[consts[d] for d in days], **kwargs)
    elif rec.freq is Freq.MONTHLY:
        # "on the 31st" falls on the last day of shorter months (bills do this),
        # instead of skipping the month the way a plain RRULE would.
        monthday = rec.monthday or (rec.anchor.day if rec.anchor else 1)
        anchor = rec.anchor or start.replace(day=1)
        interval = max(1, rec.interval)
        out: list[date] = []
        y, m = anchor.year, anchor.month
        while date(y, m, 1) < end:
            day = min(monthday, calendar.monthrange(y, m)[1])
            d = date(y, m, day)
            if start <= d < end and d >= (rec.anchor or d):
                out.append(d)
            m += interval
            while m > 12:
                m -= 12
                y += 1
        return out
    elif rec.freq is Freq.YEARLY:
        if not rec.anchor:
            return []
        rule = rrule(
            YEARLY,
            dtstart=_dt(min(rec.anchor, start)),
            bymonth=rec.anchor.month,
            bymonthday=rec.anchor.day,
            **kwargs,
        )
    else:  # pragma: no cover - exhaustive
        return []
    return [d.date() for d in rule if start <= d.date() < end]


def _dt(d: date):
    from datetime import datetime

    return datetime(d.year, d.month, d.day)


def occurs_on(rec: Recurrence, day: date) -> bool:
    return day in expand(rec, day, day + timedelta(days=1))


def commitments_on(world: World, person: str, day: date) -> list[Commitment]:
    return [
        c
        for c in world.commitments
        if c.person == person and (c.id, day) not in world.commitment_exceptions and occurs_on(c.recurrence, day)
    ]


def unavailable_on(world: World, person: str, day: date):
    return [u for u in world.unavailability if u.person == person and u.start <= day < u.end]


def occurrence_dates(world: World, scenario: Scenario, resp: Responsibility) -> list[date]:
    """Dates the responsibility must be satisfied inside the scenario window.

    For ONGOING responsibilities we evaluate on check dates: the start of the
    window plus every date inside it where something relevant changes (a permit
    expiring, a person's unavailability starting or ending).
    """
    if resp.recurrence.freq is not Freq.ONGOING:
        return expand(resp.recurrence, scenario.start, scenario.end)
    return check_dates(world, scenario, resp)


def check_dates(world: World, scenario: Scenario, resp: Responsibility) -> list[date]:
    dates = {scenario.start}
    resource_ids: set[str] = set()
    people: set[str] = set()
    for route in resp.routes:
        for req in route.requirements:
            resource_ids.add(req.target)
        people.update(world.candidates(resp, route))
    for rid in sorted(resource_ids):
        res = world.resources.get(rid)
        if res and res.valid_until:
            day_after = res.valid_until + timedelta(days=1)
            if scenario.start <= day_after < scenario.end:
                dates.add(day_after)
    for u in world.unavailability:
        if u.person in people:
            for d in (u.start, u.end):
                if scenario.start <= d < scenario.end:
                    dates.add(d)
    return sorted(dates)


def window_days(scenario: Scenario) -> int:
    return (scenario.end - scenario.start).days
