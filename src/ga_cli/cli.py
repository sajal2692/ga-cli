from __future__ import annotations

import click

from ga_cli import __version__
from ga_cli.commands import (
    accounts,
    admin,
    auth_cmd,
    compat,
    global_options,
    meta,
    presets,
    properties,
    quota,
    realtime,
    report,
    skill_cmd,
)


@click.group()
@click.version_option(version=__version__, prog_name="ga4")
@global_options
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Agent-native CLI for Google Analytics 4."""
    ctx.ensure_object(dict)


cli.add_command(auth_cmd.auth_group)
cli.add_command(accounts.accounts)
cli.add_command(properties.properties_group)
cli.add_command(admin.streams)
cli.add_command(admin.custom_dimensions)
cli.add_command(admin.custom_metrics)
cli.add_command(admin.key_events)
cli.add_command(meta.meta)
cli.add_command(compat.compat)
cli.add_command(report.report)
cli.add_command(realtime.realtime)
cli.add_command(presets.pages)
cli.add_command(presets.sources)
cli.add_command(presets.events)
cli.add_command(presets.trend)
cli.add_command(quota.quota)
cli.add_command(skill_cmd.skill_group)
