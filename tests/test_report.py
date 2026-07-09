from __future__ import annotations

import json
from typing import Any

import pytest

from ga_cli.clients import data_types
from ga_cli.commands import report as report_module
from tests.conftest import FakeDataClient, report_response

ENV = {"GA_PROPERTY": "123456789"}

INT = data_types.MetricType.TYPE_INTEGER
FLOAT = data_types.MetricType.TYPE_FLOAT


def basic_response(**kwargs: Any) -> Any:
    return report_response(
        ["date", "pagePath"],
        [("activeUsers", INT), ("engagementRate", FLOAT)],
        [
            (["20260701", "/blog/a"], ["301", "0.62"]),
            (["20260702", "/b"], ["120", "0.4"]),
        ],
        row_count=87,
        **kwargs,
    )


def test_report_envelope_golden(invoke: Any, fake_data: FakeDataClient, golden: Any) -> None:
    fake_data.report_responses = [basic_response()]
    result = invoke(
        "report", "-m", "activeUsers,engagementRate", "-d", "date,pagePath",
        "-r", "2026-07-01:2026-07-02", "--limit", "2", env=ENV,
    )
    assert result.exit_code == 0
    golden(result, "report_envelope.json")
    request = fake_data.report_requests[0]
    assert request.property == "properties/123456789"
    assert request.limit == 2
    assert request.offset == 0
    assert [m.name for m in request.metrics] == ["activeUsers", "engagementRate"]
    assert [d.name for d in request.dimensions] == ["date", "pagePath"]
    assert request.order_bys[0].metric.metric_name == "activeUsers"
    assert request.order_bys[0].desc is True
    assert fake_data.timeouts == [30.0]


def test_report_compare_golden(
    invoke: Any, fake_data: FakeDataClient, golden: Any, frozen_today: Any
) -> None:
    # Faithful to the API: each base row arrives once per range (zero-filled),
    # row_count counts base rows only.
    fake_data.report_responses = [
        report_response(
            ["date", "dateRange"],
            [("sessions", INT)],
            [
                (["20260626", "previous"], ["8"]),
                (["20260626", "current"], ["0"]),
                (["20260703", "current"], ["10"]),
                (["20260703", "previous"], ["0"]),
            ],
            row_count=2,
        )
    ]
    result = invoke("report", "-m", "sessions", "-d", "date", "-r", "7d", "--compare", "prev",
                    "-o", "date", env=ENV)
    assert result.exit_code == 0
    golden(result, "report_compare.json")
    request = fake_data.report_requests[0]
    assert [(r.start_date, r.end_date, r.name) for r in request.date_ranges] == [
        ("2026-07-03", "2026-07-09", "current"),
        ("2026-06-26", "2026-07-02", "previous"),
    ]


def test_report_multirange_has_more_uses_base_rows(
    invoke: Any, fake_data: FakeDataClient, frozen_today: Any
) -> None:
    fake_data.report_responses = [
        report_response(
            ["date", "dateRange"],
            [("sessions", INT)],
            [(["20260626", "previous"], ["8"]), (["20260626", "current"], ["0"])],
            row_count=2,
        )
    ]
    result = invoke("report", "-m", "sessions", "-d", "date", "-r", "7d", "--compare", "prev",
                    "--limit", "1", env=ENV)
    data = json.loads(result.stdout)
    assert data["returned"] == 2
    assert data["row_count"] == 2
    assert data["has_more"] is True


def test_report_all_multirange_pages_in_base_rows(
    invoke: Any, fake_data: FakeDataClient, frozen_today: Any
) -> None:
    fake_data.report_responses = [
        report_response(
            ["date", "dateRange"],
            [("sessions", INT)],
            [
                (["20260701", "current"], ["1"]),
                (["20260701", "previous"], ["0"]),
                (["20260702", "current"], ["2"]),
                (["20260702", "previous"], ["0"]),
            ],
            row_count=3,
        ),
        report_response(
            ["date", "dateRange"],
            [("sessions", INT)],
            [(["20260703", "current"], ["3"]), (["20260703", "previous"], ["0"])],
            row_count=3,
        ),
    ]
    result = invoke("report", "-m", "sessions", "-d", "date", "-r", "7d", "--compare", "prev",
                    "--all", "--limit", "2", env=ENV)
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["returned"] == 6
    assert data["has_more"] is False
    assert [(r.limit, r.offset) for r in fake_data.report_requests] == [(2, 0), (2, 2)]


def test_report_totals_quota_golden(invoke: Any, fake_data: FakeDataClient, golden: Any) -> None:
    fake_data.report_responses = [
        report_response(
            ["pagePath"],
            [("sessions", INT)],
            [(["/a"], ["4000"]), (["/b"], ["102"])],
            totals=[(["RESERVED_TOTAL"], ["4102"])],
            quota={
                "tokens_per_day": {"consumed": 14, "remaining": 199986},
                "tokens_per_hour": {"consumed": 14, "remaining": 39986},
                "concurrent_requests": {"consumed": 0, "remaining": 10},
            },
        )
    ]
    result = invoke("report", "-m", "sessions", "-d", "pagePath",
                    "-r", "2026-07-01:2026-07-02", "--totals", "--quota", env=ENV)
    assert result.exit_code == 0
    golden(result, "report_totals_quota.json")
    request = fake_data.report_requests[0]
    assert list(request.metric_aggregations) == [data_types.MetricAggregation.TOTAL]
    assert request.return_property_quota is True


def test_report_empty_golden(invoke: Any, fake_data: FakeDataClient, golden: Any) -> None:
    fake_data.report_responses = [
        report_response(["pagePath"], [("sessions", INT)], [], row_count=0)
    ]
    result = invoke("report", "-m", "sessions", "-d", "pagePath",
                    "-r", "2026-07-01:2026-07-02", env=ENV)
    assert result.exit_code == 0
    golden(result, "report_empty.json")


def test_report_fail_empty_exits_3_and_still_emits(
    invoke: Any, fake_data: FakeDataClient, golden: Any
) -> None:
    fake_data.report_responses = [
        report_response(["pagePath"], [("sessions", INT)], [], row_count=0)
    ]
    result = invoke("report", "-m", "sessions", "-d", "pagePath",
                    "-r", "2026-07-01:2026-07-02", "--fail-empty", env=ENV)
    assert result.exit_code == 3
    golden(result, "report_empty.json")


def test_report_results_only_golden(invoke: Any, fake_data: FakeDataClient, golden: Any) -> None:
    fake_data.report_responses = [basic_response()]
    result = invoke("report", "-m", "activeUsers,engagementRate", "-d", "date,pagePath",
                    "-r", "2026-07-01:2026-07-02", "--results-only", env=ENV)
    assert result.exit_code == 0
    golden(result, "report_results_only.json")


def test_report_compact(invoke: Any, fake_data: FakeDataClient) -> None:
    fake_data.report_responses = [
        report_response(["pagePath"], [("sessions", INT)], [(["/a"], ["1"])])
    ]
    result = invoke("report", "-m", "sessions", "-d", "pagePath",
                    "-r", "2026-07-01:2026-07-02", "--compact", env=ENV)
    assert result.exit_code == 0
    assert result.stdout.count("\n") == 1
    assert json.loads(result.stdout)["rows"] == [{"pagePath": "/a", "sessions": 1}]


def test_report_raw(invoke: Any, fake_data: FakeDataClient) -> None:
    fake_data.report_responses = [
        report_response(["pagePath"], [("sessions", INT)], [(["/a"], ["1"])])
    ]
    result = invoke("report", "-m", "sessions", "-d", "pagePath",
                    "-r", "2026-07-01:2026-07-02", "--raw", env=ENV)
    assert result.exit_code == 0
    raw = json.loads(result.stdout)
    assert raw["rows"][0]["dimension_values"][0]["value"] == "/a"


def test_report_all_pages(invoke: Any, fake_data: FakeDataClient) -> None:
    pages = [
        report_response(["pagePath"], [("sessions", INT)],
                        [(["/a"], ["1"]), (["/b"], ["2"])], row_count=5),
        report_response(["pagePath"], [("sessions", INT)],
                        [(["/c"], ["3"]), (["/d"], ["4"])], row_count=5),
        report_response(["pagePath"], [("sessions", INT)], [(["/e"], ["5"])], row_count=5),
    ]
    fake_data.report_responses = pages
    result = invoke("report", "-m", "sessions", "-d", "pagePath",
                    "-r", "2026-07-01:2026-07-02", "--all", "--limit", "2", env=ENV)
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert [row["pagePath"] for row in data["rows"]] == ["/a", "/b", "/c", "/d", "/e"]
    assert data["returned"] == 5
    assert data["has_more"] is False
    assert [(r.limit, r.offset) for r in fake_data.report_requests] == [(2, 0), (2, 2), (2, 4)]


def test_report_all_default_page_limit(invoke: Any, fake_data: FakeDataClient) -> None:
    fake_data.report_responses = [
        report_response(["pagePath"], [("sessions", INT)], [(["/a"], ["1"])], row_count=1)
    ]
    result = invoke("report", "-m", "sessions", "-d", "pagePath",
                    "-r", "2026-07-01:2026-07-02", "--all", env=ENV)
    assert result.exit_code == 0
    assert fake_data.report_requests[0].limit == report_module.PAGE_LIMIT


def test_report_all_cap(
    invoke: Any, fake_data: FakeDataClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(report_module, "MAX_ACCUMULATED_ROWS", 4)
    fake_data.report_responses = [
        report_response(["pagePath"], [("sessions", INT)],
                        [(["/a"], ["1"]), (["/b"], ["2"])], row_count=10),
        report_response(["pagePath"], [("sessions", INT)],
                        [(["/c"], ["3"]), (["/d"], ["4"])], row_count=10),
    ]
    result = invoke("report", "-m", "sessions", "-d", "pagePath",
                    "-r", "2026-07-01:2026-07-02", "--all", "--limit", "2", env=ENV)
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["returned"] == 4
    assert data["has_more"] is True
    assert "stopped after 4 accumulated rows" in result.stderr


def test_report_all_non_advancing_guard(invoke: Any, fake_data: FakeDataClient) -> None:
    fake_data.report_responses = [
        report_response(["pagePath"], [("sessions", INT)],
                        [(["/a"], ["1"]), (["/b"], ["2"])], row_count=5),
        report_response(["pagePath"], [("sessions", INT)], [], row_count=5),
    ]
    result = invoke("report", "-m", "sessions", "-d", "pagePath",
                    "-r", "2026-07-01:2026-07-02", "--all", "--limit", "2", env=ENV)
    assert result.exit_code == 0
    assert json.loads(result.stdout)["returned"] == 2
    assert "pagination stopped early" in result.stderr


def test_report_offset_has_more(invoke: Any, fake_data: FakeDataClient) -> None:
    fake_data.report_responses = [
        report_response(["pagePath"], [("sessions", INT)], [(["/a"], ["1"])], row_count=87)
    ]
    result = invoke("report", "-m", "sessions", "-d", "pagePath",
                    "-r", "2026-07-01:2026-07-02", "--offset", "86", env=ENV)
    data = json.loads(result.stdout)
    assert data["has_more"] is False
    assert fake_data.report_requests[0].offset == 86


def test_report_filters_compile_into_request(invoke: Any, fake_data: FakeDataClient) -> None:
    fake_data.report_responses = [
        report_response(["pagePath"], [("sessions", INT)], [(["/a"], ["1"])])
    ]
    result = invoke("report", "-m", "sessions", "-d", "pagePath",
                    "-r", "2026-07-01:2026-07-02",
                    "-f", "pagePath=^/blog", "-f", "sessions>10", env=ENV)
    assert result.exit_code == 0
    request = fake_data.report_requests[0]
    assert request.dimension_filter.filter.field_name == "pagePath"
    assert request.metric_filter.filter.field_name == "sessions"


def test_report_order_none(invoke: Any, fake_data: FakeDataClient) -> None:
    fake_data.report_responses = [
        report_response(["pagePath"], [("sessions", INT)], [(["/a"], ["1"])])
    ]
    result = invoke("report", "-m", "sessions", "-d", "pagePath",
                    "-r", "2026-07-01:2026-07-02", "-o", "none", env=ENV)
    assert result.exit_code == 0
    assert len(fake_data.report_requests[0].order_bys) == 0


@pytest.mark.parametrize(
    ("args", "fragment"),
    [
        (("-m", ",".join(f"m{i}" for i in range(11))), "At most 10 metrics"),
        (("-m", "sessions", "-d", ",".join(f"d{i}" for i in range(10))), "At most 9 dimensions"),
        (("-m", "sessions", "-r", "7d", "-r", "28d", "--compare", "prev"), "--compare"),
        (("-m", "sessions", "-f", "a=^/x", "--filter-json", "{}"), "--filter-json"),
        (("-m", "sessions", "-o", "bounceRate"), "Order field"),
        (("-m", "sessions", "--raw", "--all"), "--raw cannot be combined"),
        (("-m", "sessions", "-r", "junk"), "Invalid date range"),
        (("-m", "sessions", "-f", "sessions=@x"), "not valid for metric"),
        (("-m", "sessions", "--limit", "0"), "--limit"),
        (("-m", ""), "at least one metric"),
    ],
)
def test_report_usage_errors(
    invoke: Any, fake_data: FakeDataClient, args: tuple[str, ...], fragment: str
) -> None:
    result = invoke("report", *args, env=ENV)
    assert result.exit_code == 2
    assert fragment in result.stderr
    assert result.stdout == ""
    assert fake_data.report_requests == []


def test_report_alias_resolution(invoke: Any, fake_data: FakeDataClient, tmp_path: Any) -> None:
    config = tmp_path / "config.toml"
    config.write_text('[properties]\nblog = "123456789"\n')
    fake_data.report_responses = [
        report_response(["pagePath"], [("sessions", INT)], [(["/a"], ["1"])])
    ]
    result = invoke("report", "-P", "blog", "-m", "sessions", "-d", "pagePath",
                    "-r", "2026-07-01:2026-07-02",
                    env={"GA_CONFIG": str(config), "GA_PROPERTY": None})
    assert result.exit_code == 0
    assert fake_data.report_requests[0].property == "properties/123456789"


def test_report_unknown_alias(invoke: Any, fake_data: FakeDataClient) -> None:
    result = invoke("report", "-P", "nope", "-m", "sessions", env=ENV)
    assert result.exit_code == 2
    assert "Unknown property 'nope'" in result.stderr


def test_report_default_property_from_config(
    invoke: Any, fake_data: FakeDataClient, tmp_path: Any
) -> None:
    config = tmp_path / "config.toml"
    config.write_text('default_property = "properties/555"\n')
    fake_data.report_responses = [
        report_response(["pagePath"], [("sessions", INT)], [(["/a"], ["1"])])
    ]
    result = invoke("report", "-m", "sessions", "-r", "2026-07-01:2026-07-02",
                    env={"GA_CONFIG": str(config), "GA_PROPERTY": None})
    assert result.exit_code == 0
    assert fake_data.report_requests[0].property == "properties/555"
