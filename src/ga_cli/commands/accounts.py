from __future__ import annotations

from typing import Any

import click

from ga_cli import output, props
from ga_cli.commands import global_options
from ga_cli.errors import handle_errors


@click.command("accounts")
@global_options
@click.pass_context
@handle_errors
def accounts(ctx: click.Context) -> None:
    """List accessible GA4 accounts and their properties."""
    result: list[dict[str, Any]] = []
    for summary in props.account_summaries(ctx):
        entry: dict[str, Any] = {"account": summary.account, "display": summary.display_name}
        properties = [
            {"property": prop.property, "display": prop.display_name}
            for prop in summary.property_summaries
        ]
        if properties:
            entry["properties"] = properties
        result.append(entry)
    output.emit(result)
