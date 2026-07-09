from __future__ import annotations

import click
import pytest

from ga_cli import flatten, orders
from ga_cli.clients import data_types
from tests.conftest import report_response

METRICS = ["sessions", "activeUsers"]
DIMS = ["pagePath", "date"]


def test_default_order_first_metric_desc() -> None:
    result = orders.build((), METRICS, DIMS)
    assert result is not None
    assert result[0].metric.metric_name == "sessions"
    assert result[0].desc is True


def test_explicit_orders() -> None:
    result = orders.build(("-activeUsers", "pagePath"), METRICS, DIMS)
    assert result is not None
    assert result[0].metric.metric_name == "activeUsers"
    assert result[0].desc is True
    assert result[1].dimension.dimension_name == "pagePath"
    assert result[1].desc is False


def test_order_none() -> None:
    assert orders.build(("none",), METRICS, DIMS) is None
    with pytest.raises(click.UsageError):
        orders.build(("none", "date"), METRICS, DIMS)


def test_order_unknown_field() -> None:
    with pytest.raises(click.UsageError):
        orders.build(("bounceRate",), METRICS, DIMS)


@pytest.mark.parametrize(
    ("value", "metric_type", "expected"),
    [
        ("412", data_types.MetricType.TYPE_INTEGER, 412),
        ("", data_types.MetricType.TYPE_INTEGER, ""),
        ("0.62", data_types.MetricType.TYPE_FLOAT, 0.62),
        ("12.5", data_types.MetricType.TYPE_SECONDS, 12.5),
        ("3.5", data_types.MetricType.TYPE_CURRENCY, 3.5),
        ("nope", data_types.MetricType.TYPE_FLOAT, "nope"),
        ("17", data_types.MetricType.TYPE_STANDARD, 17),
        ("17.5", data_types.MetricType.METRIC_TYPE_UNSPECIFIED, 17.5),
        ("(other)", data_types.MetricType.METRIC_TYPE_UNSPECIFIED, "(other)"),
    ],
)
def test_metric_coercion(value: str, metric_type: object, expected: object) -> None:
    assert flatten.coerce_metric(value, metric_type) == expected


@pytest.mark.parametrize(
    ("name", "wire", "expected"),
    [
        ("date", "20260701", "2026-07-01"),
        ("firstSessionDate", "20260701", "2026-07-01"),
        ("dateHour", "2026070114", "2026-07-01T14"),
        ("dateHourMinute", "202607011432", "2026-07-01T14:32"),
        ("yearMonth", "202607", "2026-07"),
        ("yearWeek", "202628", "2026-W28"),
        ("date", "(not set)", "(not set)"),
        ("pagePath", "20260701", "20260701"),
        ("country", "(other)", "(other)"),
    ],
)
def test_dimension_normalization(name: str, wire: str, expected: str) -> None:
    assert flatten.normalize_dim(name, wire) == expected


def test_flatten_rows_multirange_rename() -> None:
    response = report_response(
        ["date", "dateRange"],
        [("activeUsers", data_types.MetricType.TYPE_INTEGER)],
        [(["20260701", "current"], ["10"]), (["20250701", "previous"], ["7"])],
    )
    rows = flatten.flatten_rows(response)
    assert rows == [
        {"date": "2026-07-01", "date_range": "current", "activeUsers": 10},
        {"date": "2025-07-01", "date_range": "previous", "activeUsers": 7},
    ]


def test_flatten_totals_single_and_multi() -> None:
    single = report_response(
        ["pagePath"],
        [("sessions", data_types.MetricType.TYPE_INTEGER)],
        [(["/a"], ["1"])],
        totals=[(["RESERVED_TOTAL"], ["4102"])],
    )
    assert flatten.flatten_totals(single) == {"sessions": 4102}
    multi = report_response(
        ["dateRange", "pagePath"],
        [("sessions", data_types.MetricType.TYPE_INTEGER)],
        [(["current", "/a"], ["1"])],
        totals=[(["current", "RESERVED_TOTAL"], ["10"]), (["previous", "RESERVED_TOTAL"], ["8"])],
    )
    assert flatten.flatten_totals(multi) == [
        {"date_range": "current", "sessions": 10},
        {"date_range": "previous", "sessions": 8},
    ]
    empty = report_response(["pagePath"], [("sessions", data_types.MetricType.TYPE_INTEGER)], [])
    assert flatten.flatten_totals(empty) is None
