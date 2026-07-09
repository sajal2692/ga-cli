from __future__ import annotations

import json
from typing import Any

import pytest

from ga_cli.clients import data_types
from tests.conftest import FakeAdminClient, FakeDataClient, report_response

ENV = {"GA_PROPERTY": "123456789"}
INT = data_types.MetricType.TYPE_INTEGER


def simple_response() -> Any:
    return report_response(
        ["pagePath"], [("sessions", INT)], [(["/a"], ["10"]), (["/b"], ["3"])], row_count=2
    )


def test_table_mode_renders_columns(invoke: Any, fake_data: FakeDataClient) -> None:
    fake_data.report_responses = [simple_response()]
    result = invoke("report", "-m", "sessions", "-d", "pagePath",
                    "-r", "2026-07-01:2026-07-02", "--table", env=ENV)
    assert result.exit_code == 0
    assert "pagePath" in result.stdout
    assert "sessions" in result.stdout
    with pytest.raises(json.JSONDecodeError):
        json.loads(result.stdout)
    assert "property=properties/123456789" in result.stderr


def test_table_mode_empty_rows_note_on_stderr(invoke: Any, fake_data: FakeDataClient) -> None:
    fake_data.report_responses = [
        report_response(["pagePath"], [("sessions", INT)], [], row_count=0)
    ]
    result = invoke("report", "-m", "sessions", "-d", "pagePath",
                    "-r", "2026-07-01:2026-07-02", "--table", env=ENV)
    assert result.exit_code == 0
    assert result.stdout == ""
    assert "No rows returned." in result.stderr


def test_auto_table_stays_json_when_not_tty(invoke: Any, fake_data: FakeDataClient) -> None:
    fake_data.report_responses = [simple_response()]
    result = invoke("report", "-m", "sessions", "-d", "pagePath",
                    "-r", "2026-07-01:2026-07-02",
                    env={**ENV, "GA_AUTO_TABLE": "1"})
    assert json.loads(result.stdout)["row_count"] == 2


def test_bare_array_table(invoke: Any, fake_admin: FakeAdminClient) -> None:
    result = invoke("properties", "list", "--table")
    assert result.exit_code == 0
    assert "sajalsharma.com" in result.stdout


def test_bare_object_table(invoke: Any, fake_data: FakeDataClient) -> None:
    fake_data.report_responses = [
        report_response(
            [], [("activeUsers", INT)], [([], ["1"])],
            quota={
                "tokens_per_day": {"consumed": 1, "remaining": 2},
                "tokens_per_hour": {"consumed": 1, "remaining": 2},
                "concurrent_requests": {"consumed": 0, "remaining": 10},
            },
        )
    ]
    result = invoke("quota", "--table", env=ENV)
    assert result.exit_code == 0
    assert "tokens_per_day" in result.stdout


def test_meta_table(invoke: Any, fake_data: FakeDataClient) -> None:
    fake_data.metadata = data_types.Metadata(
        dimensions=[{"api_name": "pagePath", "ui_name": "Page path", "category": "Page"}],
        metrics=[{"api_name": "sessions", "ui_name": "Sessions", "category": "Session"}],
    )
    result = invoke("meta", "--table", env=ENV)
    assert result.exit_code == 0
    assert "dimension" in result.stdout
    assert "metric" in result.stdout


def test_table_compact_conflict(invoke: Any, fake_admin: FakeAdminClient) -> None:
    result = invoke("accounts", "--table", "--compact")
    assert result.exit_code == 2
    assert "--table and --compact cannot be combined." in result.stderr
    assert result.stdout == ""


def test_auto_table_renders_table_when_tty(
    invoke: Any, fake_data: FakeDataClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from ga_cli import output as output_module

    monkeypatch.setattr(
        output_module, "sys", SimpleNamespace(stdout=SimpleNamespace(isatty=lambda: True))
    )
    fake_data.report_responses = [simple_response()]
    result = invoke("report", "-m", "sessions", "-d", "pagePath",
                    "-r", "2026-07-01:2026-07-02", env={**ENV, "GA_AUTO_TABLE": "1"})
    assert result.exit_code == 0
    with pytest.raises(json.JSONDecodeError):
        json.loads(result.stdout)
    assert "pagePath" in result.stdout


def test_compact_overrides_auto_table(
    invoke: Any, fake_data: FakeDataClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from ga_cli import output as output_module

    monkeypatch.setattr(
        output_module, "sys", SimpleNamespace(stdout=SimpleNamespace(isatty=lambda: True))
    )
    fake_data.report_responses = [simple_response()]
    result = invoke("report", "-m", "sessions", "-d", "pagePath",
                    "-r", "2026-07-01:2026-07-02", "--compact",
                    env={**ENV, "GA_AUTO_TABLE": "1"})
    assert result.stdout.count("\n") == 1
    assert json.loads(result.stdout)["row_count"] == 2


def test_no_ansi_in_json_output(invoke: Any, fake_data: FakeDataClient) -> None:
    fake_data.report_responses = [simple_response()]
    result = invoke("report", "-m", "sessions", "-d", "pagePath",
                    "-r", "2026-07-01:2026-07-02", env=ENV)
    assert "\x1b" not in result.stdout
    json.loads(result.stdout)


def test_unicode_not_escaped(invoke: Any, fake_data: FakeDataClient) -> None:
    fake_data.report_responses = [
        report_response(["country"], [("sessions", INT)], [(["日本"], ["5"])])
    ]
    result = invoke("report", "-m", "sessions", "-d", "country",
                    "-r", "2026-07-01:2026-07-02", env=ENV)
    assert "日本" in result.stdout
