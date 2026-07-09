from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

import click

GA_TOKEN_RE = re.compile(r"^(today|yesterday|\d+daysAgo)$")
RELATIVE_RE = re.compile(r"^(\d+)d$")
NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")

RANGE_FORMS = (
    "Accepted forms: today, yesterday, Nd (7d, 28d), wtd, mtd, qtd, ytd, YYYY-MM-DD, "
    "YYYY-MM-DD:YYYY-MM-DD, GA tokens (28daysAgo:yesterday, 7daysAgo), "
    "optionally prefixed with name= (launch=2026-06-01:2026-06-15)."
)


@dataclass
class ResolvedRange:
    name: str
    start: str
    end: str


def _today() -> date:
    return date.today()


def _invalid(spec: str) -> click.UsageError:
    return click.UsageError(f"Invalid date range '{spec}'. {RANGE_FORMS}")


def _parse_iso(value: str, spec: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise _invalid(spec) from None


def _quarter_start(today: date) -> date:
    return today.replace(month=3 * ((today.month - 1) // 3) + 1, day=1)


def _parse_bounds(spec_range: str, spec: str) -> tuple[str, str]:
    today = _today()
    if spec_range == "today":
        return today.isoformat(), today.isoformat()
    if spec_range == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday.isoformat(), yesterday.isoformat()
    match = RELATIVE_RE.match(spec_range)
    if match:
        days = int(match.group(1))
        if days < 1:
            raise _invalid(spec)
        return (today - timedelta(days=days - 1)).isoformat(), today.isoformat()
    if spec_range == "wtd":
        return (today - timedelta(days=today.weekday())).isoformat(), today.isoformat()
    if spec_range == "mtd":
        return today.replace(day=1).isoformat(), today.isoformat()
    if spec_range == "qtd":
        return _quarter_start(today).isoformat(), today.isoformat()
    if spec_range == "ytd":
        return today.replace(month=1, day=1).isoformat(), today.isoformat()
    if ":" in spec_range:
        start, _, end = spec_range.partition(":")
        start_date = _side(start, spec)
        end_date = _side(end, spec)
        if isinstance(start_date, date) and isinstance(end_date, date) and start_date > end_date:
            raise click.UsageError(f"Invalid date range '{spec}': start is after end.")
        return _bound_str(start_date), _bound_str(end_date)
    if GA_TOKEN_RE.match(spec_range):
        return spec_range, "today"
    if re.match(r"^\d{4}-\d{2}-\d{2}$", spec_range):
        day = _parse_iso(spec_range, spec)
        return day.isoformat(), day.isoformat()
    raise _invalid(spec)


def _side(value: str, spec: str) -> date | str:
    if GA_TOKEN_RE.match(value):
        return value
    if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return _parse_iso(value, spec)
    raise _invalid(spec)


def _bound_str(bound: date | str) -> str:
    return bound.isoformat() if isinstance(bound, date) else bound


def parse_range(spec: str, default_name: str) -> ResolvedRange:
    name = default_name
    spec_range = spec
    if "=" in spec:
        name, _, spec_range = spec.partition("=")
        if not NAME_RE.match(name) or not spec_range:
            raise _invalid(spec)
    start, end = _parse_bounds(spec_range, spec)
    return ResolvedRange(name=name, start=start, end=end)


def _default_name(index: int) -> str:
    if index == 0:
        return "current"
    if index == 1:
        return "previous"
    return f"range_{index}"


def _to_date(bound: str) -> date:
    today = _today()
    if bound == "today":
        return today
    if bound == "yesterday":
        return today - timedelta(days=1)
    match = re.match(r"^(\d+)daysAgo$", bound)
    if match:
        return today - timedelta(days=int(match.group(1)))
    return date.fromisoformat(bound)


def _compare_range(first: ResolvedRange, mode: str) -> ResolvedRange:
    start = _to_date(first.start)
    end = _to_date(first.end)
    if mode == "prev":
        length = (end - start).days + 1
        prev_end = start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=length - 1)
        return ResolvedRange("previous", prev_start.isoformat(), prev_end.isoformat())
    try:
        yoy_start = start.replace(year=start.year - 1)
    except ValueError:
        yoy_start = start.replace(year=start.year - 1, day=28)
    try:
        yoy_end = end.replace(year=end.year - 1)
    except ValueError:
        yoy_end = end.replace(year=end.year - 1, day=28)
    return ResolvedRange("previous", yoy_start.isoformat(), yoy_end.isoformat())


def parse_ranges(specs: tuple[str, ...], compare: str | None) -> list[ResolvedRange]:
    if compare and len(specs) > 1:
        raise click.UsageError("--compare cannot be combined with multiple --range values.")
    if len(specs) > 4:
        raise click.UsageError("At most 4 date ranges are allowed per report.")
    if not specs:
        specs = ("28d",)
    ranges = [parse_range(spec, _default_name(index)) for index, spec in enumerate(specs)]
    names = [entry.name for entry in ranges]
    if len(set(names)) != len(names):
        raise click.UsageError("Date range names must be unique.")
    if compare:
        ranges.append(_compare_range(ranges[0], compare))
    return ranges
