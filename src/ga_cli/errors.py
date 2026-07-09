from __future__ import annotations

import functools
import re
import sys
from collections.abc import Callable
from typing import Any, TypeVar

import click
from google.api_core import exceptions as api_exceptions
from google.auth import exceptions as auth_exceptions

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_EMPTY = 3
EXIT_AUTH = 4
EXIT_NOT_FOUND = 5
EXIT_PERMISSION = 6
EXIT_QUOTA = 7
EXIT_RETRYABLE = 8

NO_CREDENTIALS_MESSAGE = 'No Google credentials found. Run "ga auth guide" for setup steps.'

FIELD_HINT = 'Hint: run "ga meta --search <field>" to find valid metric and dimension names.'

RETRYABLE_EXCEPTIONS = (
    api_exceptions.DeadlineExceeded,
    api_exceptions.ServiceUnavailable,
    api_exceptions.InternalServerError,
    api_exceptions.Aborted,
    api_exceptions.RetryError,
    ConnectionError,
)

F = TypeVar("F", bound=Callable[..., Any])


class CliError(Exception):
    def __init__(self, message: str, code: int = EXIT_ERROR):
        super().__init__(message)
        self.code = code


def _api_message(exc: Exception) -> str:
    message = getattr(exc, "message", None) or str(exc)
    return str(message).strip()


def _permission_denied(
    exc: api_exceptions.PermissionDenied, obj: dict[str, Any]
) -> tuple[int, str]:
    message = _api_message(exc)
    if re.search(r"quota|rate limit|too many|exhausted", message, re.IGNORECASE):
        return EXIT_QUOTA, f'{message} Check remaining tokens with "ga quota".'
    prop = obj.get("_resolved_property")
    if prop:
        principal = obj.get("_principal") or 'your credentials principal (see "ga auth check")'
        return EXIT_PERMISSION, (
            f"Access denied to {prop}. Grant Viewer access to {principal} in "
            'GA4 Admin > Property access management, or check the property ID with "ga properties".'
        )
    return EXIT_PERMISSION, f"Permission denied: {message}"


def _map_exception(exc: Exception, obj: dict[str, Any]) -> tuple[int, str]:
    if isinstance(exc, CliError):
        return exc.code, str(exc)
    if isinstance(exc, auth_exceptions.DefaultCredentialsError):
        return EXIT_AUTH, NO_CREDENTIALS_MESSAGE
    if isinstance(exc, auth_exceptions.TransportError):
        return EXIT_RETRYABLE, f"Transient failure: {exc} Retry the command."
    if isinstance(exc, auth_exceptions.GoogleAuthError):
        return EXIT_AUTH, (
            f'Authentication failed: {exc} Run "ga auth check" to inspect credentials.'
        )
    if isinstance(exc, api_exceptions.Unauthenticated):
        return EXIT_AUTH, (
            f'Authentication failed: {_api_message(exc)} '
            'Run "ga auth check" to inspect credentials.'
        )
    if isinstance(exc, (api_exceptions.ResourceExhausted, api_exceptions.TooManyRequests)):
        return EXIT_QUOTA, f'{_api_message(exc)} Check remaining tokens with "ga quota".'
    if isinstance(exc, api_exceptions.PermissionDenied):
        return _permission_denied(exc, obj)
    if isinstance(exc, api_exceptions.NotFound):
        return EXIT_NOT_FOUND, (
            f'Not found: {_api_message(exc)} '
            'Run "ga properties" to list available properties.'
        )
    if isinstance(exc, api_exceptions.InvalidArgument):
        message = _api_message(exc)
        if re.search(r"metric|dimension", message, re.IGNORECASE):
            message = f"{message} {FIELD_HINT}"
        return EXIT_USAGE, message
    if isinstance(exc, RETRYABLE_EXCEPTIONS):
        message = _api_message(exc)
        if re.search(r"invalid_grant|invalid_rapt|expired or revoked", message, re.IGNORECASE):
            return EXIT_AUTH, (
                f'Credentials rejected: {message} '
                'Re-authenticate, or run "ga auth guide" for setup steps.'
            )
        return EXIT_RETRYABLE, f"Transient failure: {message} Retry the command."
    return EXIT_ERROR, str(exc)


def handle_errors(f: F) -> F:
    @functools.wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        ctx = click.get_current_context()
        obj = ctx.obj or {}
        if obj.get("table") and obj.get("compact"):
            raise click.UsageError("--table and --compact cannot be combined.")
        try:
            return f(*args, **kwargs)
        except click.ClickException:
            raise
        except click.exceptions.Abort:
            raise
        except Exception as exc:
            if obj.get("debug"):
                raise
            code, message = _map_exception(exc, obj)
            click.echo(f"Error: {message}", err=True)
            sys.exit(code)

    return wrapper  # type: ignore[return-value]
