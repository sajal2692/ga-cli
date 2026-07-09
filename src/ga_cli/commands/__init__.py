from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

import click
from click.core import ParameterSource

F = TypeVar("F", bound=Callable[..., Any])

RANGE_HELP = (
    "Date range (repeatable, max 4): today, 7d, mtd, 2026-06-01:2026-06-15, "
    "28daysAgo:yesterday, name=RANGE."
)


def _store_global(ctx: click.Context, param: click.Parameter, value: Any) -> Any:
    obj = ctx.ensure_object(dict)
    name = param.name or ""
    source = ctx.get_parameter_source(name)
    explicit = source is not None and source is not ParameterSource.DEFAULT
    if explicit or name not in obj:
        obj[name] = value
    if explicit and name == "credentials_flag":
        obj["credentials_from"] = (
            "--credentials" if source is ParameterSource.COMMANDLINE else "GA_CREDENTIALS"
        )
    if explicit and name == "property_flag":
        obj["property_from"] = "-P" if source is ParameterSource.COMMANDLINE else "GA_PROPERTY"
    return value


_GLOBAL_OPTIONS = [
    click.option(
        "-P",
        "--property",
        "property_flag",
        envvar="GA_PROPERTY",
        expose_value=False,
        callback=_store_global,
        help="GA4 property: numeric ID, properties/<id>, or a config alias.",
    ),
    click.option(
        "--credentials",
        "credentials_flag",
        envvar="GA_CREDENTIALS",
        expose_value=False,
        callback=_store_global,
        help="Path to a service account JSON key.",
    ),
    click.option(
        "--config",
        "config_flag",
        envvar="GA_CONFIG",
        expose_value=False,
        callback=_store_global,
        help="Config file (default ~/.config/ga-cli/config.toml).",
    ),
    click.option(
        "--table",
        "table",
        is_flag=True,
        expose_value=False,
        callback=_store_global,
        help="Render a table instead of JSON.",
    ),
    click.option(
        "--compact",
        "compact",
        is_flag=True,
        expose_value=False,
        callback=_store_global,
        help="Single-line JSON output.",
    ),
    click.option(
        "--timeout",
        "timeout",
        type=float,
        default=30.0,
        show_default=True,
        expose_value=False,
        callback=_store_global,
        help="Per-request timeout in seconds.",
    ),
    click.option(
        "--debug",
        "debug",
        is_flag=True,
        expose_value=False,
        callback=_store_global,
        help="Re-raise errors with tracebacks.",
    ),
]


def global_options(f: F) -> F:
    for option in reversed(_GLOBAL_OPTIONS):
        f = option(f)
    return f


def split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]
