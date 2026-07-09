from __future__ import annotations

from typing import Any

import pytest
from google.api_core import exceptions as api_exceptions

from ga_cli.errors import FIELD_HINT
from tests.conftest import FakeDataClient

ENV = {"GA_PROPERTY": "123456789"}


def run_with_error(invoke: Any, fake_data: FakeDataClient, error: Exception) -> Any:
    fake_data.error = error
    return invoke("report", "-m", "sessions", "-r", "2026-07-01:2026-07-02", env=ENV)


def test_unauthenticated_exit_4(invoke: Any, fake_data: FakeDataClient) -> None:
    result = run_with_error(invoke, fake_data, api_exceptions.Unauthenticated("bad token"))
    assert result.exit_code == 4
    assert "ga4 auth check" in result.stderr
    assert result.stdout == ""


def test_permission_denied_exit_6_with_remediation(
    invoke: Any, fake_data: FakeDataClient
) -> None:
    result = run_with_error(invoke, fake_data, api_exceptions.PermissionDenied("denied"))
    assert result.exit_code == 6
    assert "Access denied to properties/123456789" in result.stderr
    assert "Grant Viewer access" in result.stderr
    assert 'ga4 properties' in result.stderr


def test_permission_denied_quota_reason_exit_7(invoke: Any, fake_data: FakeDataClient) -> None:
    result = run_with_error(
        invoke, fake_data, api_exceptions.PermissionDenied("Property quota exhausted")
    )
    assert result.exit_code == 7
    assert 'ga4 quota' in result.stderr


def test_not_found_exit_5(invoke: Any, fake_data: FakeDataClient) -> None:
    result = run_with_error(invoke, fake_data, api_exceptions.NotFound("no such property"))
    assert result.exit_code == 5


def test_resource_exhausted_exit_7(invoke: Any, fake_data: FakeDataClient) -> None:
    result = run_with_error(invoke, fake_data, api_exceptions.ResourceExhausted("tokens gone"))
    assert result.exit_code == 7
    assert 'Check remaining tokens with "ga4 quota".' in result.stderr


def test_too_many_requests_exit_7(invoke: Any, fake_data: FakeDataClient) -> None:
    result = run_with_error(invoke, fake_data, api_exceptions.TooManyRequests("slow down"))
    assert result.exit_code == 7


def test_invalid_argument_exit_2_with_hint(invoke: Any, fake_data: FakeDataClient) -> None:
    result = run_with_error(
        invoke, fake_data, api_exceptions.InvalidArgument("Field sessionz is not a valid metric.")
    )
    assert result.exit_code == 2
    assert "sessionz" in result.stderr
    assert FIELD_HINT in result.stderr


def test_invalid_argument_no_hint_without_field(invoke: Any, fake_data: FakeDataClient) -> None:
    result = run_with_error(invoke, fake_data, api_exceptions.InvalidArgument("bad request"))
    assert result.exit_code == 2
    assert FIELD_HINT not in result.stderr


@pytest.mark.parametrize(
    "error",
    [
        api_exceptions.DeadlineExceeded("timed out"),
        api_exceptions.ServiceUnavailable("503"),
        api_exceptions.InternalServerError("500"),
        api_exceptions.Aborted("aborted"),
        api_exceptions.RetryError("gave up", cause=Exception("x")),
        ConnectionError("refused"),
    ],
)
def test_retryable_exit_8(invoke: Any, fake_data: FakeDataClient, error: Exception) -> None:
    result = run_with_error(invoke, fake_data, error)
    assert result.exit_code == 8
    assert "Transient failure" in result.stderr


def test_auth_failure_wrapped_as_transport_error_exit_4(
    invoke: Any, fake_data: FakeDataClient
) -> None:
    # gRPC surfaces refresh failures as UNAVAILABLE; classify by message instead.
    result = run_with_error(
        invoke,
        fake_data,
        api_exceptions.ServiceUnavailable(
            "Getting metadata from plugin failed with error: "
            "('invalid_grant: Account has been deleted', ...)"
        ),
    )
    assert result.exit_code == 4
    assert "Credentials rejected" in result.stderr


def test_unclassified_exit_1(invoke: Any, fake_data: FakeDataClient) -> None:
    result = run_with_error(invoke, fake_data, RuntimeError("boom"))
    assert result.exit_code == 1
    assert "boom" in result.stderr
    assert result.stdout == ""


def test_debug_reraises(invoke: Any, fake_data: FakeDataClient) -> None:
    fake_data.error = RuntimeError("boom")
    with pytest.raises(RuntimeError, match="boom"):
        invoke("report", "-m", "sessions", "-r", "2026-07-01:2026-07-02", "--debug", env=ENV)
