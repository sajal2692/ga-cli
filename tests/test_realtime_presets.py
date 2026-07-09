from __future__ import annotations

import json
from typing import Any

import pytest

from ga_cli.clients import data_types
from tests.conftest import FakeDataClient, realtime_response, report_response

ENV = {"GA_PROPERTY": "123456789"}
INT = data_types.MetricType.TYPE_INTEGER


def test_realtime_golden(invoke: Any, fake_data: FakeDataClient, golden: Any) -> None:
    fake_data.realtime_response = realtime_response(
        ["unifiedScreenName"], [("activeUsers", INT)], [(["Home"], ["5"])]
    )
    result = invoke("realtime", "-d", "unifiedScreenName", env=ENV)
    assert result.exit_code == 0
    golden(result, "realtime.json")
    request = fake_data.realtime_requests[0]
    assert request.minute_ranges[0].start_minutes_ago == 29
    assert request.minute_ranges[0].end_minutes_ago == 0
    assert [m.name for m in request.metrics] == ["activeUsers"]
    assert request.limit == 20


def test_realtime_minutes_and_flags(invoke: Any, fake_data: FakeDataClient) -> None:
    fake_data.realtime_response = realtime_response(
        [], [("activeUsers", INT)], [([], ["3"])]
    )
    result = invoke("realtime", "--minutes", "5", "--limit", "7", "--results-only", env=ENV)
    assert result.exit_code == 0
    assert json.loads(result.stdout) == [{"activeUsers": 3}]
    request = fake_data.realtime_requests[0]
    assert request.minute_ranges[0].start_minutes_ago == 4
    assert request.limit == 7


def test_realtime_fail_empty(invoke: Any, fake_data: FakeDataClient) -> None:
    fake_data.realtime_response = realtime_response([], [("activeUsers", INT)], [], row_count=0)
    result = invoke("realtime", "--fail-empty", env=ENV)
    assert result.exit_code == 3
    assert json.loads(result.stdout)["rows"] == []


def test_realtime_raw(invoke: Any, fake_data: FakeDataClient) -> None:
    fake_data.realtime_response = realtime_response(
        [], [("activeUsers", INT)], [([], ["3"])]
    )
    result = invoke("realtime", "--raw", env=ENV)
    assert result.exit_code == 0
    assert json.loads(result.stdout)["rows"][0]["metric_values"][0]["value"] == "3"


def test_realtime_minutes_out_of_range(invoke: Any, fake_data: FakeDataClient) -> None:
    result = invoke("realtime", "--minutes", "31", env=ENV)
    assert result.exit_code == 2


PRESETS = [
    ("pages", ["pagePath"], ["screenPageViews", "activeUsers"], "screenPageViews", True),
    ("sources", ["sessionDefaultChannelGroup"], ["sessions", "activeUsers"], "sessions", True),
    ("events", ["eventName"], ["eventCount", "activeUsers"], "eventCount", True),
    ("trend", ["date"], ["activeUsers", "sessions", "screenPageViews"], "date", False),
]


@pytest.mark.usefixtures("frozen_today")
@pytest.mark.parametrize(("name", "dims", "metrics", "order_field", "order_desc"), PRESETS)
def test_presets_build_expected_requests(
    invoke: Any,
    fake_data: FakeDataClient,
    name: str,
    dims: list[str],
    metrics: list[str],
    order_field: str,
    order_desc: bool,
) -> None:
    fake_data.report_responses = [
        report_response(dims, [(m, INT) for m in metrics],
                        [(["x"] * len(dims), ["1"] * len(metrics))])
    ]
    result = invoke(name, env=ENV)
    assert result.exit_code == 0
    request = fake_data.report_requests[0]
    assert [d.name for d in request.dimensions] == dims
    assert [m.name for m in request.metrics] == metrics
    assert request.limit == 10
    order = request.order_bys[0]
    if order_desc:
        assert order.metric.metric_name == order_field
        assert order.desc is True
    else:
        assert order.dimension.dimension_name == order_field
        assert order.desc is False
    ranges = request.date_ranges
    assert (ranges[0].start_date, ranges[0].end_date) == ("2026-06-12", "2026-07-09")


def test_preset_filter_classification_uses_preset_metrics(
    invoke: Any, fake_data: FakeDataClient, frozen_today: Any
) -> None:
    fake_data.report_responses = [
        report_response(["pagePath"], [("screenPageViews", INT), ("activeUsers", INT)],
                        [(["/a"], ["1", "2"])])
    ]
    result = invoke("pages", "-f", "screenPageViews>100", "-f", "pagePath=^/blog", env=ENV)
    assert result.exit_code == 0
    request = fake_data.report_requests[0]
    assert request.metric_filter.filter.field_name == "screenPageViews"
    assert request.dimension_filter.filter.field_name == "pagePath"


def test_preset_rejects_unknown_flags(invoke: Any, fake_data: FakeDataClient) -> None:
    result = invoke("pages", "--totals", env=ENV)
    assert result.exit_code == 2


def test_preset_compare(invoke: Any, fake_data: FakeDataClient, frozen_today: Any) -> None:
    fake_data.report_responses = [
        report_response(["date", "dateRange"], [("activeUsers", INT)],
                        [(["20260701", "current"], ["1"])])
    ]
    result = invoke("trend", "-r", "7d", "--compare", "prev", env=ENV)
    assert result.exit_code == 0
    assert len(fake_data.report_requests[0].date_ranges) == 2


def test_preset_epilog_shows_equivalent(invoke: Any) -> None:
    result = invoke("pages", "--help")
    assert "Equivalent: ga report -m screenPageViews,activeUsers -d pagePath" in result.stdout
