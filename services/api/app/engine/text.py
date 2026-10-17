"""Small wording helpers shared by the engine's plain-language messages."""

from __future__ import annotations

from datetime import date


def cap(text: str) -> str:
    """Capitalise the first letter only (labels may contain names: 'Mr Silva')."""
    return text[:1].upper() + text[1:] if text else text


def plural(n: int, one: str, many: str | None = None) -> str:
    return one if n == 1 else (many or one + "s")


def fmt_day(d: date) -> str:
    """'Thu 5 Nov' (no leading zero)."""
    return f"{d.strftime('%a')} {d.day} {d.strftime('%b')}"


def fmt_date(d: date) -> str:
    """'20 Nov 2026' (no leading zero)."""
    return f"{d.day} {d.strftime('%b %Y')}"


def join_and(items: list[str]) -> str:
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]
