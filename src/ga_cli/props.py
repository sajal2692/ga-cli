from __future__ import annotations

import os
import re

import click

from ga_cli import clients, config

ID_RE = re.compile(r"^\d+$")
PROPERTY_RE = re.compile(r"^properties/\d+$")

NO_PROPERTY_MESSAGE = (
    "No property specified. Pass -P, set GA_PROPERTY, or set default_property in "
    '~/.config/ga-cli/config.toml. Run "ga4 properties" to list available properties.'
)


def canonicalize(value: str, cfg: config.Config, *, source: str) -> str:
    value = value.strip()
    if ID_RE.match(value):
        return f"properties/{value}"
    if PROPERTY_RE.match(value):
        return value
    target = cfg.aliases.get(value)
    if target is not None:
        target = target.strip()
        if ID_RE.match(target):
            return f"properties/{target}"
        if PROPERTY_RE.match(target):
            return target
        raise click.UsageError(
            f"Alias '{value}' in {cfg.path} points to invalid property '{target}'. "
            "Expected a numeric ID or properties/<id>."
        )
    aliases = ", ".join(sorted(cfg.aliases)) if cfg.aliases else "none defined"
    raise click.UsageError(
        f"Unknown property '{value}' (from {source}). "
        f"Expected a numeric ID, properties/<id>, or a config alias ({aliases})."
    )


def account_summaries(ctx: click.Context) -> list:  # type: ignore[type-arg]
    obj = ctx.obj
    if "_account_summaries" not in obj:
        client = clients.get_admin_client(ctx)
        request = clients.admin_v1beta.ListAccountSummariesRequest(page_size=200)
        pager = client.list_account_summaries(request=request, timeout=obj["timeout"])
        obj["_account_summaries"] = list(pager)
    summaries: list = obj["_account_summaries"]  # type: ignore[type-arg]
    return summaries


def resolve(ctx: click.Context, *, required: bool = True) -> str | None:
    obj = ctx.obj
    if "_resolved_property" not in obj:
        obj["_resolved_property"] = _resolve(ctx)
    prop: str | None = obj["_resolved_property"]
    if prop is None and required:
        raise click.UsageError(NO_PROPERTY_MESSAGE)
    return prop


def _resolve(ctx: click.Context) -> str | None:
    cfg = config.for_ctx(ctx)
    flag = ctx.obj.get("property_flag")
    if flag:
        return canonicalize(flag, cfg, source="-P")
    env = os.environ.get("GA_PROPERTY")
    if env:
        return canonicalize(env, cfg, source="GA_PROPERTY")
    if cfg.default_property:
        return canonicalize(cfg.default_property, cfg, source="config default_property")
    properties = [
        summary.property
        for account in account_summaries(ctx)
        for summary in account.property_summaries
    ]
    if len(properties) == 1:
        click.echo(f"Using {properties[0]} (only accessible property).", err=True)
        return str(properties[0])
    return None
