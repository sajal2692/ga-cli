from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner, Result

from ga_cli import clients, dates
from ga_cli.cli import cli
from ga_cli.clients import admin_v1beta, data_types

GOLDEN_DIR = Path(__file__).parent / "golden"

FROZEN_TODAY = date(2026, 7, 9)


class FakeDataClient:
    def __init__(self) -> None:
        self.report_responses: list[Any] = []
        self.realtime_response: Any = None
        self.metadata: Any = None
        self.compat_response: Any = None
        self.compat_responses: list[Any] = []
        self.error: Exception | None = None
        self.report_requests: list[Any] = []
        self.realtime_requests: list[Any] = []
        self.metadata_requests: list[Any] = []
        self.compat_requests: list[Any] = []
        self.timeouts: list[float | None] = []

    def run_report(self, request: Any = None, timeout: float | None = None) -> Any:
        if self.error:
            raise self.error
        self.report_requests.append(data_types.RunReportRequest(request))
        self.timeouts.append(timeout)
        index = min(len(self.report_requests), len(self.report_responses)) - 1
        return self.report_responses[index]

    def run_realtime_report(self, request: Any = None, timeout: float | None = None) -> Any:
        if self.error:
            raise self.error
        self.realtime_requests.append(data_types.RunRealtimeReportRequest(request))
        self.timeouts.append(timeout)
        return self.realtime_response

    def get_metadata(self, request: Any = None, timeout: float | None = None) -> Any:
        if self.error:
            raise self.error
        self.metadata_requests.append(request)
        self.timeouts.append(timeout)
        return self.metadata

    def check_compatibility(self, request: Any = None, timeout: float | None = None) -> Any:
        if self.error:
            raise self.error
        self.compat_requests.append(request)
        self.timeouts.append(timeout)
        if self.compat_responses:
            index = min(len(self.compat_requests), len(self.compat_responses)) - 1
            entry = self.compat_responses[index]
            if isinstance(entry, Exception):
                raise entry
            return entry
        return self.compat_response


class FakeAdminClient:
    def __init__(self) -> None:
        self.account_summaries: list[Any] = []
        self.property: Any = None
        self.data_streams: list[Any] = []
        self.custom_dimensions: list[Any] = []
        self.custom_metrics: list[Any] = []
        self.key_events: list[Any] = []
        self.error: Exception | None = None
        self.calls: list[tuple[str, Any, float | None]] = []

    def _record(self, name: str, request: Any, timeout: float | None) -> None:
        if self.error:
            raise self.error
        self.calls.append((name, request, timeout))

    def list_account_summaries(self, request: Any = None, timeout: float | None = None) -> Any:
        self._record("list_account_summaries", request, timeout)
        return list(self.account_summaries)

    def get_property(self, request: Any = None, timeout: float | None = None) -> Any:
        self._record("get_property", request, timeout)
        return self.property

    def list_data_streams(self, request: Any = None, timeout: float | None = None) -> Any:
        self._record("list_data_streams", request, timeout)
        return list(self.data_streams)

    def list_custom_dimensions(self, request: Any = None, timeout: float | None = None) -> Any:
        self._record("list_custom_dimensions", request, timeout)
        return list(self.custom_dimensions)

    def list_custom_metrics(self, request: Any = None, timeout: float | None = None) -> Any:
        self._record("list_custom_metrics", request, timeout)
        return list(self.custom_metrics)

    def list_key_events(self, request: Any = None, timeout: float | None = None) -> Any:
        self._record("list_key_events", request, timeout)
        return list(self.key_events)


def report_response(
    dim_headers: list[str],
    metric_headers: list[tuple[str, Any]],
    rows: list[tuple[list[str], list[str]]],
    row_count: int | None = None,
    totals: list[tuple[list[str], list[str]]] | None = None,
    quota: dict[str, Any] | None = None,
) -> Any:
    response = data_types.RunReportResponse(
        dimension_headers=[{"name": name} for name in dim_headers],
        metric_headers=[{"name": name, "type_": type_} for name, type_ in metric_headers],
        rows=[
            {
                "dimension_values": [{"value": value} for value in dims],
                "metric_values": [{"value": value} for value in metrics],
            }
            for dims, metrics in rows
        ],
        row_count=row_count if row_count is not None else len(rows),
    )
    if totals:
        response.totals = [
            {
                "dimension_values": [{"value": value} for value in dims],
                "metric_values": [{"value": value} for value in metrics],
            }
            for dims, metrics in totals
        ]
    if quota:
        response.property_quota = quota
    return response


def realtime_response(
    dim_headers: list[str],
    metric_headers: list[tuple[str, Any]],
    rows: list[tuple[list[str], list[str]]],
    row_count: int | None = None,
) -> Any:
    return data_types.RunRealtimeReportResponse(
        dimension_headers=[{"name": name} for name in dim_headers],
        metric_headers=[{"name": name, "type_": type_} for name, type_ in metric_headers],
        rows=[
            {
                "dimension_values": [{"value": value} for value in dims],
                "metric_values": [{"value": value} for value in metrics],
            }
            for dims, metrics in rows
        ],
        row_count=row_count if row_count is not None else len(rows),
    )


def account_summary(
    account_id: str, display: str, properties: list[tuple[str, str]]
) -> Any:
    return admin_v1beta.AccountSummary(
        name=f"accountSummaries/{account_id}",
        account=f"accounts/{account_id}",
        display_name=display,
        property_summaries=[
            {"property": prop, "display_name": prop_display} for prop, prop_display in properties
        ],
    )


DEFAULT_SUMMARIES = [
    account_summary(
        "100",
        "Sajal",
        [("properties/123456789", "sajalsharma.com"), ("properties/987654321", "side project")],
    )
]


@pytest.fixture
def fake_data(monkeypatch: pytest.MonkeyPatch) -> FakeDataClient:
    client = FakeDataClient()
    monkeypatch.setattr(clients, "get_data_client", lambda ctx: client)
    return client


@pytest.fixture
def fake_admin(monkeypatch: pytest.MonkeyPatch) -> FakeAdminClient:
    client = FakeAdminClient()
    client.account_summaries = list(DEFAULT_SUMMARIES)
    monkeypatch.setattr(clients, "get_admin_client", lambda ctx: client)
    return client


@pytest.fixture
def frozen_today(monkeypatch: pytest.MonkeyPatch) -> date:
    monkeypatch.setattr(dates, "_today", lambda: FROZEN_TODAY)
    return FROZEN_TODAY


@pytest.fixture
def invoke(tmp_path: Path) -> Any:
    runner = CliRunner()

    def _invoke(*args: str, env: dict[str, str | None] | None = None) -> Result:
        base_env: dict[str, str | None] = {
            "GA_CONFIG": str(tmp_path / "missing-config.toml"),
            "GA_PROPERTY": None,
            "GA_CREDENTIALS": None,
            "GA_AUTO_TABLE": None,
            "GOOGLE_APPLICATION_CREDENTIALS": None,
        }
        if env:
            base_env.update(env)
        return runner.invoke(cli, list(args), env=base_env, catch_exceptions=False)

    return _invoke


def assert_golden(result: Result, name: str) -> None:
    expected = (GOLDEN_DIR / name).read_text()
    assert result.stdout == expected


@pytest.fixture
def golden() -> Any:
    return assert_golden
