from __future__ import annotations

import json
from typing import Any

from ga_cli.clients import data_types
from tests.conftest import FakeDataClient

ENV = {"GA_PROPERTY": "123456789"}


def make_metadata() -> Any:
    return data_types.Metadata(
        name="properties/123456789/metadata",
        dimensions=[
            {
                "api_name": "pagePath",
                "ui_name": "Page path",
                "category": "Page / screen",
                "description": "The path of the page.",
            },
            {
                "api_name": "customEvent:author",
                "ui_name": "Author",
                "category": "Custom",
                "custom_definition": True,
                "description": "Event-scoped author.",
            },
        ],
        metrics=[
            {
                "api_name": "engagementRate",
                "ui_name": "Engagement rate",
                "category": "Session",
                "type_": data_types.MetricType.TYPE_FLOAT,
                "description": "Engaged sessions divided by sessions.",
                "expression": "engagedSessions/sessions",
            },
            {
                "api_name": "userEngagementDuration",
                "ui_name": "User engagement",
                "category": "Session",
                "type_": data_types.MetricType.TYPE_SECONDS,
                "description": "Time the app was in the foreground.",
            },
        ],
    )


def test_meta_search_golden(invoke: Any, fake_data: FakeDataClient, golden: Any) -> None:
    fake_data.metadata = make_metadata()
    result = invoke("meta", "--search", "engagement", "--type", "metrics", env=ENV)
    assert result.exit_code == 0
    golden(result, "meta.json")
    assert fake_data.metadata_requests[0].name == "properties/123456789/metadata"


def test_meta_all_fields(invoke: Any, fake_data: FakeDataClient) -> None:
    fake_data.metadata = make_metadata()
    result = invoke("meta", env=ENV)
    data = json.loads(result.stdout)
    assert [d["name"] for d in data["dimensions"]] == ["pagePath", "customEvent:author"]
    assert data["dimensions"][1]["custom"] is True
    assert "description" not in data["dimensions"][0]


def test_meta_custom_only(invoke: Any, fake_data: FakeDataClient) -> None:
    fake_data.metadata = make_metadata()
    result = invoke("meta", "--custom", env=ENV)
    data = json.loads(result.stdout)
    assert [d["name"] for d in data["dimensions"]] == ["customEvent:author"]
    assert data["metrics"] == []


def test_meta_full(invoke: Any, fake_data: FakeDataClient) -> None:
    fake_data.metadata = make_metadata()
    result = invoke("meta", "--full", "--search", "engagementRate", env=ENV)
    data = json.loads(result.stdout)
    metric = data["metrics"][0]
    assert metric["description"] == "Engaged sessions divided by sessions."
    assert metric["type"] == "TYPE_FLOAT"
    assert metric["expression"] == "engagedSessions/sessions"


def test_meta_search_matches_description(invoke: Any, fake_data: FakeDataClient) -> None:
    fake_data.metadata = make_metadata()
    result = invoke("meta", "--search", "foreground", env=ENV)
    data = json.loads(result.stdout)
    assert [m["name"] for m in data["metrics"]] == ["userEngagementDuration"]


def test_compat_golden(invoke: Any, fake_data: FakeDataClient, golden: Any) -> None:
    fake_data.compat_response = data_types.CheckCompatibilityResponse(
        metric_compatibilities=[
            {
                "metric_metadata": {"api_name": "purchaserRate"},
                "compatibility": data_types.Compatibility.INCOMPATIBLE,
            },
            {
                "metric_metadata": {"api_name": "unrelatedMetric"},
                "compatibility": data_types.Compatibility.INCOMPATIBLE,
            },
        ],
        dimension_compatibilities=[],
    )
    result = invoke("compat", "-m", "purchaserRate,sessions", "-d", "date", env=ENV)
    assert result.exit_code == 0
    golden(result, "compat.json")
    request = fake_data.compat_requests[0]
    assert request.compatibility_filter == data_types.Compatibility.INCOMPATIBLE


def test_compat_compatible(invoke: Any, fake_data: FakeDataClient) -> None:
    fake_data.compat_response = data_types.CheckCompatibilityResponse()
    result = invoke("compat", "-m", "sessions", env=ENV)
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "compatible": True,
        "incompatible_metrics": [],
        "incompatible_dimensions": [],
    }


def test_compat_requires_fields(invoke: Any, fake_data: FakeDataClient) -> None:
    result = invoke("compat", env=ENV)
    assert result.exit_code == 2
    assert "Provide --metrics and/or --dims" in result.stderr


def test_compat_incompatible_request_is_data_not_error(
    invoke: Any, fake_data: FakeDataClient
) -> None:
    # The live API rejects an incompatible combination outright; the command
    # must catch it, attribute blame per side, and exit 0 with data.
    from google.api_core import exceptions as api_exceptions

    fake_data.compat_responses = [
        api_exceptions.InvalidArgument("The dimensions and metrics are incompatible."),
        data_types.CheckCompatibilityResponse(
            metric_compatibilities=[
                {
                    "metric_metadata": {"api_name": "addToCarts"},
                    "compatibility": data_types.Compatibility.INCOMPATIBLE,
                }
            ]
        ),
        data_types.CheckCompatibilityResponse(dimension_compatibilities=[]),
    ]
    result = invoke("compat", "-m", "addToCarts,sessions", "-d", "itemName", env=ENV)
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "compatible": False,
        "incompatible_metrics": [{"name": "addToCarts", "reason": "INCOMPATIBLE"}],
        "incompatible_dimensions": [],
    }
    assert len(fake_data.compat_requests) == 3


def test_compat_invalid_field_name_still_errors(invoke: Any, fake_data: FakeDataClient) -> None:
    from google.api_core import exceptions as api_exceptions

    fake_data.compat_responses = [
        api_exceptions.InvalidArgument("Field bogusMetric is not a valid metric.")
    ]
    result = invoke("compat", "-m", "bogusMetric", env=ENV)
    assert result.exit_code == 2
    assert "bogusMetric" in result.stderr
    assert result.stdout == ""


def test_quota_golden(invoke: Any, fake_data: FakeDataClient, golden: Any) -> None:
    from tests.conftest import report_response

    fake_data.report_responses = [
        report_response(
            [],
            [("activeUsers", data_types.MetricType.TYPE_INTEGER)],
            [([], ["1"])],
            quota={
                "tokens_per_day": {"consumed": 14, "remaining": 199986},
                "tokens_per_hour": {"consumed": 14, "remaining": 39986},
                "concurrent_requests": {"consumed": 0, "remaining": 10},
            },
        )
    ]
    result = invoke("quota", env=ENV)
    assert result.exit_code == 0
    golden(result, "quota.json")
    request = fake_data.report_requests[0]
    assert request.limit == 1
    assert request.return_property_quota is True
    assert request.date_ranges[0].start_date == "today"
