from __future__ import annotations

from typing import Any

import click

from ga_cli import clients, config, output, props
from ga_cli.commands import global_options
from ga_cli.errors import handle_errors


@click.group("properties", invoke_without_command=True)
@global_options
@click.pass_context
def properties_group(ctx: click.Context) -> None:
    """List and inspect GA4 properties."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(properties_list)


@properties_group.command("list")
@global_options
@click.pass_context
@handle_errors
def properties_list(ctx: click.Context) -> None:
    """List properties visible to the credentials."""
    result = []
    for summary in props.account_summaries(ctx):
        for prop in summary.property_summaries:
            result.append(
                {
                    "id": prop.property.split("/")[-1],
                    "property": prop.property,
                    "display": prop.display_name,
                    "account": summary.account,
                }
            )
    output.emit(result)


@properties_group.command("get")
@click.argument("property_arg", metavar="[PROPERTY]", required=False)
@global_options
@click.pass_context
@handle_errors
def properties_get(ctx: click.Context, property_arg: str | None) -> None:
    """Show details for one property."""
    if property_arg:
        prop = props.canonicalize(property_arg, config.for_ctx(ctx), source="argument")
        ctx.obj["_resolved_property"] = prop
    else:
        resolved = props.resolve(ctx)
        assert resolved is not None
        prop = resolved
    detail = clients.get_admin_client(ctx).get_property(
        request=clients.admin_v1beta.GetPropertyRequest(name=prop),
        timeout=ctx.obj["timeout"],
    )
    result: dict[str, Any] = {
        "id": detail.name.split("/")[-1],
        "property": detail.name,
        "display": detail.display_name,
    }
    if detail.time_zone:
        result["time_zone"] = detail.time_zone
    if detail.currency_code:
        result["currency"] = detail.currency_code
    if detail.industry_category:
        result["industry"] = detail.industry_category.name
    if detail.service_level:
        result["service_level"] = detail.service_level.name
    if detail.create_time:
        result["created"] = detail.create_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    output.emit(result)
