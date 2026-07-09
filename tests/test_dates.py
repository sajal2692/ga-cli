from __future__ import annotations

import click
import pytest

from ga_cli import dates


@pytest.mark.usefixtures("frozen_today")
@pytest.mark.parametrize(
    ("spec", "start", "end"),
    [
        ("today", "2026-07-09", "2026-07-09"),
        ("yesterday", "2026-07-08", "2026-07-08"),
        ("1d", "2026-07-09", "2026-07-09"),
        ("7d", "2026-07-03", "2026-07-09"),
        ("28d", "2026-06-12", "2026-07-09"),
        ("wtd", "2026-07-06", "2026-07-09"),
        ("mtd", "2026-07-01", "2026-07-09"),
        ("qtd", "2026-07-01", "2026-07-09"),
        ("ytd", "2026-01-01", "2026-07-09"),
        ("2026-06-15", "2026-06-15", "2026-06-15"),
        ("2026-06-01:2026-06-15", "2026-06-01", "2026-06-15"),
        ("28daysAgo:yesterday", "28daysAgo", "yesterday"),
        ("7daysAgo", "7daysAgo", "today"),
        ("2026-06-01:yesterday", "2026-06-01", "yesterday"),
    ],
)
def test_range_grammar(spec: str, start: str, end: str) -> None:
    resolved = dates.parse_range(spec, "current")
    assert (resolved.start, resolved.end) == (start, end)
    assert resolved.name == "current"


@pytest.mark.usefixtures("frozen_today")
def test_named_range() -> None:
    resolved = dates.parse_range("launch=2026-06-01:2026-06-15", "current")
    assert resolved.name == "launch"
    assert resolved.start == "2026-06-01"


@pytest.mark.usefixtures("frozen_today")
@pytest.mark.parametrize(
    "spec",
    ["", "0d", "junk", "2026-13-01", "2026-06-15:2026-06-01", "=7d", "bad name=7d", "7dd"],
)
def test_invalid_ranges(spec: str) -> None:
    with pytest.raises(click.UsageError):
        dates.parse_range(spec, "current")


@pytest.mark.usefixtures("frozen_today")
def test_default_names_and_limits() -> None:
    ranges = dates.parse_ranges(("7d", "mtd", "ytd"), None)
    assert [r.name for r in ranges] == ["current", "previous", "range_2"]
    with pytest.raises(click.UsageError):
        dates.parse_ranges(("1d", "2d", "3d", "4d", "5d"), None)
    with pytest.raises(click.UsageError):
        dates.parse_ranges(("a=7d", "a=8d"), None)


@pytest.mark.usefixtures("frozen_today")
def test_default_range_is_28d() -> None:
    ranges = dates.parse_ranges((), None)
    assert len(ranges) == 1
    assert ranges[0].start == "2026-06-12"
    assert ranges[0].end == "2026-07-09"


@pytest.mark.usefixtures("frozen_today")
def test_compare_prev() -> None:
    ranges = dates.parse_ranges(("28d",), "prev")
    assert [r.name for r in ranges] == ["current", "previous"]
    assert (ranges[0].start, ranges[0].end) == ("2026-06-12", "2026-07-09")
    assert (ranges[1].start, ranges[1].end) == ("2026-05-15", "2026-06-11")


@pytest.mark.usefixtures("frozen_today")
def test_compare_yoy() -> None:
    ranges = dates.parse_ranges(("2026-06-01:2026-06-15",), "yoy")
    assert (ranges[1].start, ranges[1].end) == ("2025-06-01", "2025-06-15")


@pytest.mark.usefixtures("frozen_today")
def test_compare_prev_resolves_ga_tokens() -> None:
    ranges = dates.parse_ranges(("7daysAgo",), "prev")
    assert (ranges[0].start, ranges[0].end) == ("7daysAgo", "today")
    assert (ranges[1].start, ranges[1].end) == ("2026-06-24", "2026-07-01")


@pytest.mark.usefixtures("frozen_today")
def test_compare_rejects_multiple_ranges() -> None:
    with pytest.raises(click.UsageError):
        dates.parse_ranges(("7d", "28d"), "prev")
