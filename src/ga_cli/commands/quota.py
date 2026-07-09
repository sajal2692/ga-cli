from __future__ import annotations

import click

from ga_cli import clients, flatten, output, props
from ga_cli.commands import global_options
from ga_cli.errors import handle_errors


@click.command("quota")
@global_options
@click.pass_context
@handle_errors
def quota(ctx: click.Context) -> None:
    """Show remaining report token quota for the property."""
    prop = props.resolve(ctx)
    response = clients.get_data_client(ctx).run_report(
        request=clients.data_types.RunReportRequest(
            property=prop,
            metrics=[clients.data_types.Metric(name="activeUsers")],
            date_ranges=[clients.data_types.DateRange(start_date="today", end_date="today")],
            limit=1,
            return_property_quota=True,
        ),
        timeout=ctx.obj["timeout"],
    )
    output.emit(flatten.quota_dict(response.property_quota))
