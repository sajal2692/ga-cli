from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click

from ga_cli import config
from ga_cli.errors import EXIT_AUTH, CliError

SCOPE = "https://www.googleapis.com/auth/analytics.readonly"


@dataclass
class CredentialInfo:
    credentials: Any
    source: str
    path: str | None = None
    principal: str | None = None
    type: str = "service_account"


def _from_service_account(path_value: str, source: str) -> CredentialInfo:
    from google.oauth2 import service_account

    path = Path(path_value).expanduser()
    if not path.is_file():
        raise CliError(
            f'Credentials file not found: {path} (from {source}). '
            'Run "ga auth guide" for setup steps.',
            EXIT_AUTH,
        )
    try:
        info = json.loads(path.read_text())
        credentials = service_account.Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
            str(path), scopes=[SCOPE]
        )
    except (ValueError, KeyError) as exc:
        raise CliError(
            f"Invalid service account key at {path} (from {source}): {exc}. "
            'Run "ga auth guide" for setup steps.',
            EXIT_AUTH,
        ) from exc
    return CredentialInfo(
        credentials=credentials,
        source=source,
        path=str(path),
        principal=info.get("client_email"),
        type="service_account",
    )


def _from_adc() -> CredentialInfo:
    import google.auth
    from google.oauth2 import credentials as user_credentials
    from google.oauth2 import service_account

    credentials, _ = google.auth.default(scopes=[SCOPE])
    adc_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    source = "GOOGLE_APPLICATION_CREDENTIALS" if adc_path else "adc"
    if isinstance(credentials, service_account.Credentials):
        cred_type = "service_account"
    elif isinstance(credentials, user_credentials.Credentials):
        cred_type = "user"
    else:
        cred_type = "adc"
    return CredentialInfo(
        credentials=credentials,
        source=source,
        path=adc_path,
        principal=getattr(credentials, "service_account_email", None),
        type=cred_type,
    )


def resolve(ctx: click.Context) -> CredentialInfo:
    obj = ctx.obj
    flag = obj.get("credentials_flag")
    if flag:
        source = obj.get("credentials_from", "--credentials")
        info = _from_service_account(flag, source)
    else:
        cfg = config.for_ctx(ctx)
        if cfg.credentials:
            info = _from_service_account(cfg.credentials, "config")
        else:
            info = _from_adc()
    if info.principal:
        obj["_principal"] = info.principal
    return info


def credentials_for_ctx(ctx: click.Context) -> CredentialInfo:
    obj = ctx.obj
    if "_credentials" not in obj:
        obj["_credentials"] = resolve(ctx)
    info: CredentialInfo = obj["_credentials"]
    return info
