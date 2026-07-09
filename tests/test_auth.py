from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from google.auth import exceptions as auth_exceptions

from ga_cli.clients import data_types
from tests.conftest import FakeAdminClient, FakeDataClient, report_response

SA_JSON = json.dumps(
    {"type": "service_account", "client_email": "ga-reader@my-proj.iam.gserviceaccount.com"}
)


@pytest.fixture
def fake_sa(monkeypatch: pytest.MonkeyPatch) -> None:
    from google.oauth2 import service_account

    monkeypatch.setattr(
        service_account.Credentials,
        "from_service_account_file",
        staticmethod(lambda filename, **kwargs: object()),
    )


@pytest.fixture
def sa_file(tmp_path: Path) -> Path:
    path = tmp_path / "sa.json"
    path.write_text(SA_JSON)
    return path


def test_auth_check_env_source(
    invoke: Any, fake_admin: FakeAdminClient, fake_sa: None, sa_file: Path
) -> None:
    result = invoke("auth", "check", env={"GA_CREDENTIALS": str(sa_file)})
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert list(data) == [
        "ok",
        "credentials_source",
        "credentials_path",
        "principal",
        "type",
        "accessible_properties",
    ]
    assert data["ok"] is True
    assert data["credentials_source"] == "GA_CREDENTIALS"
    assert data["credentials_path"] == str(sa_file)
    assert data["principal"] == "ga-reader@my-proj.iam.gserviceaccount.com"
    assert data["type"] == "service_account"
    assert data["accessible_properties"] == 2


def test_auth_check_flag_beats_env(
    invoke: Any, fake_admin: FakeAdminClient, fake_sa: None, sa_file: Path, tmp_path: Path
) -> None:
    other = tmp_path / "other.json"
    other.write_text(SA_JSON)
    result = invoke(
        "auth", "check", "--credentials", str(other), env={"GA_CREDENTIALS": str(sa_file)}
    )
    data = json.loads(result.stdout)
    assert data["credentials_source"] == "--credentials"
    assert data["credentials_path"] == str(other)


def test_auth_check_config_source(
    invoke: Any, fake_admin: FakeAdminClient, fake_sa: None, sa_file: Path, tmp_path: Path
) -> None:
    config = tmp_path / "config.toml"
    config.write_text(f'credentials = "{sa_file}"\ndefault_property = "properties/123456789"\n')
    result = invoke("auth", "check", env={"GA_CONFIG": str(config)})
    data = json.loads(result.stdout)
    assert data["credentials_source"] == "config"
    assert data["default_property"] == "properties/123456789"


def test_auth_check_ping(
    invoke: Any,
    fake_admin: FakeAdminClient,
    fake_data: FakeDataClient,
    fake_sa: None,
    sa_file: Path,
) -> None:
    fake_data.report_responses = [
        report_response(
            [],
            [("activeUsers", data_types.MetricType.TYPE_INTEGER)],
            [([], ["1"])],
            quota={
                "tokens_per_day": {"consumed": 1, "remaining": 199999},
                "tokens_per_hour": {"consumed": 1, "remaining": 39999},
                "concurrent_requests": {"consumed": 0, "remaining": 10},
            },
        )
    ]
    result = invoke(
        "auth", "check", "--ping",
        env={"GA_CREDENTIALS": str(sa_file), "GA_PROPERTY": "123456789"},
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ping_ok"] is True
    assert data["quota"]["tokens_per_day"]["remaining"] == 199999
    assert data["default_property"] == "properties/123456789"


def test_auth_check_missing_file_exit_4(invoke: Any, fake_admin: FakeAdminClient) -> None:
    result = invoke("auth", "check", env={"GA_CREDENTIALS": "/nonexistent/sa.json"})
    assert result.exit_code == 4
    assert "Credentials file not found" in result.stderr
    assert 'ga auth guide' in result.stderr
    assert result.stdout == ""


def test_auth_check_no_credentials_exit_4(
    invoke: Any, fake_admin: FakeAdminClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import google.auth

    def raise_default(*args: Any, **kwargs: Any) -> Any:
        raise auth_exceptions.DefaultCredentialsError("no creds")

    monkeypatch.setattr(google.auth, "default", raise_default)
    result = invoke("auth", "check")
    assert result.exit_code == 4
    assert result.stderr.strip() == (
        'Error: No Google credentials found. Run "ga auth guide" for setup steps.'
    )


def test_auth_guide_text(invoke: Any) -> None:
    result = invoke("auth", "guide")
    assert result.exit_code == 0
    assert "analyticsdata.googleapis.com" in result.stdout
    assert "analyticsadmin.googleapis.com" in result.stdout
    assert "ga auth check --ping" in result.stdout
    assert result.stderr == ""


def test_invalid_sa_json_exit_4(
    invoke: Any, fake_admin: FakeAdminClient, tmp_path: Path
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    result = invoke("auth", "check", env={"GA_CREDENTIALS": str(bad)})
    assert result.exit_code == 4
    assert result.stdout == ""
