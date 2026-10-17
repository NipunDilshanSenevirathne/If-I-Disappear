from datetime import date

from app.engine.model import Freq, Recurrence, Unavailability
from app.engine.timeutil import check_dates, expand, occurs_on
from app.engine.tri import Tri, t_and, t_or, worst

from .helpers import access, once, people, res, resp, route, scenario, weekly, world

T, F, U = Tri.T, Tri.F, Tri.U


def test_conjunction():
    assert t_and([]) is T
    assert t_and([T, T]) is T
    assert t_and([T, U]) is U
    assert t_and([U, F]) is F
    assert worst([T, U, T]) is U


def test_alternatives():
    assert t_or([]) is U  # no recorded way is unknown, never success
    assert t_or([F, F]) is F
    assert t_or([F, U]) is U
    assert t_or([U, T]) is T


def test_every_second_thursday():
    rec = Recurrence(Freq.WEEKLY, interval=2, weekdays=(3,), anchor=date(2026, 11, 12))
    days = expand(rec, date(2026, 11, 1), date(2027, 1, 30))
    assert days == [date(2026, 11, 12), date(2026, 11, 26), date(2026, 12, 10), date(2026, 12, 24), date(2027, 1, 7), date(2027, 1, 21)]


def test_window_is_half_open():
    rec = Recurrence(Freq.MONTHLY, monthday=5)
    assert expand(rec, date(2026, 11, 5), date(2027, 1, 5)) == [date(2026, 11, 5), date(2026, 12, 5)]


def test_monthly_31st_falls_on_last_day():
    rec = Recurrence(Freq.MONTHLY, monthday=31)
    assert expand(rec, date(2026, 11, 1), date(2027, 3, 1)) == [
        date(2026, 11, 30),
        date(2026, 12, 31),
        date(2027, 1, 31),
        date(2027, 2, 28),
    ]


def test_once_and_yearly():
    assert expand(once(date(2026, 11, 20)), date(2026, 11, 1), date(2027, 1, 30)) == [date(2026, 11, 20)]
    assert expand(once(date(2027, 2, 1)), date(2026, 11, 1), date(2027, 1, 30)) == []
    yearly = Recurrence(Freq.YEARLY, anchor=date(2020, 12, 15))
    assert expand(yearly, date(2026, 11, 1), date(2027, 1, 30)) == [date(2026, 12, 15)]
    assert occurs_on(weekly(3), date(2026, 11, 5))  # a Thursday


def test_ongoing_checks_on_changes():
    w = world(*people())
    w.resources["permit"] = res("permit", valid_until=date(2026, 11, 20))
    r = resp("drive", route("rt", "drive", access("permit")), owners=["appa"])
    w.responsibilities["drive"] = r
    w.unavailability.append(Unavailability("u1", "appa", date(2026, 11, 10), date(2026, 11, 12), "trip"))
    days = check_dates(w, scenario(), r)
    assert days == [date(2026, 11, 1), date(2026, 11, 10), date(2026, 11, 12), date(2026, 11, 21)]
