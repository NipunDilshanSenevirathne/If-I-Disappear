"""Shared helpers: import path for the API package, and the metric shape used in reports."""

from __future__ import annotations

import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "services" / "api"
if str(API) not in sys.path:
    sys.path.insert(0, str(API))


@dataclass
class Metric:
    name: str
    value: str | None  # what people read; None means "not run"
    target: str | None = None
    status: str = "info"  # pass | fail | not run | info
    note: str | None = None
    num: float | None = None
    den: float | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None or k in ("value", "status")}


@dataclass
class Section:
    id: str
    title: str
    summary: str
    metrics: list[Metric] = field(default_factory=list)
    details: list[str] = field(default_factory=list)  # markdown lines for the written report

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "metrics": [m.to_dict() for m in self.metrics],
            "details": self.details,
        }


def ratio(
    name: str, num: int, den: int, *, target_pct: float | None = None, note: str | None = None, lower_is_better: bool = False
) -> Metric:
    if den == 0:
        return Metric(name, "n/a", None, "info", note, num, den)
    pct = 100.0 * num / den
    value = f"{pct:.0f}% ({num}/{den})"
    if target_pct is None:
        return Metric(name, value, None, "info", note, num, den)
    ok = pct <= target_pct if lower_is_better else pct >= target_pct
    if target_pct == 100 and not lower_is_better:
        target = "100%"
    elif target_pct == 0 and lower_is_better:
        target = "0%"
    else:
        target = f"{'≤' if lower_is_better else '≥'} {target_pct:g}%"
    return Metric(name, value, target, "pass" if ok else "fail", note, num, den)


def count(name: str, n: int, *, target: int | None = None, at_most: bool = True, note: str | None = None) -> Metric:
    if target is None:
        return Metric(name, str(n), None, "info", note, n, None)
    ok = n <= target if at_most else n >= target
    return Metric(name, str(n), f"{'≤' if at_most else '≥'} {target}", "pass" if ok else "fail", note, n, None)


def not_run(name: str, why: str, target: str | None = None) -> Metric:
    return Metric(name, None, target, "not run", why)
