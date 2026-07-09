from __future__ import annotations

import json
import os

import pytest
from click.testing import CliRunner

from ga_cli.cli import cli

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(os.environ.get("GA_E2E") != "1", reason="GA_E2E=1 not set"),
]


def run(*args: str):  # type: ignore[no-untyped-def]
    return CliRunner().invoke(cli, list(args), catch_exceptions=False)


def test_auth_check_ping() -> None:
    result = run("auth", "check", "--ping")
    assert result.exit_code == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["ping_ok"] is True


def test_meta_search_sessions() -> None:
    result = run("meta", "--search", "sessions")
    assert result.exit_code == 0, result.stderr
    data = json.loads(result.stdout)
    assert any(metric["name"] == "sessions" for metric in data["metrics"])


def test_trend_7d() -> None:
    result = run("trend", "-r", "7d")
    assert result.exit_code == 0, result.stderr
    data = json.loads(result.stdout)
    assert set(data) >= {"property", "date_ranges", "rows", "row_count", "returned", "has_more"}
