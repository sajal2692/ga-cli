from __future__ import annotations

import sys
from typing import Any

import click

from ga_cli import clients, flatten, output, props
from ga_cli.commands import global_options, split_csv
from ga_cli.commands.report import API_MAX_DIMENSIONS, API_MAX_LIMIT, API_MAX_METRICS
from ga_cli.errors import EXIT_EMPTY, handle_errors


@click.command("realtime")
@click.option("-m", "--metrics", "metrics_csv", default="activeUsers", show_default=True,
              help="Comma-separated realtime metrics.")
@click.option("-d", "--dims", "dims_csv", default="",
              help="Comma-separated realtime dimensions.")
@click.option("--minutes", type=click.IntRange(1, 30), default=30, show_default=True,
              help="Window size in minutes.")
@click.option("--limit", type=click.IntRange(1, API_MAX_LIMIT), default=20, show_default=True,
              help="Max rows to return.")
@click.option("--fail-empty", is_flag=True, help="Exit 3 when zero rows.")
@click.option("--results-only", is_flag=True, help="Emit the bare rows array.")
@click.option("--raw", is_flag=True, help="Emit the raw API response without flattening.")
@global_options
@click.pass_context
@handle_errors
def realtime(
    ctx: click.Context,
    metrics_csv: str,
    dims_csv: str,
    minutes: int,
    limit: int,
    fail_empty: bool,
    results_only: bool,
    raw: bool,
) -> None:
    """Report activity from the last 30 minutes."""
    metric_names = split_csv(metrics_csv)
    dimension_names = split_csv(dims_csv)
    if not metric_names:
        raise click.UsageError("-m/--metrics requires at least one metric name.")
    if len(metric_names) > API_MAX_METRICS:
        raise click.UsageError(f"At most {API_MAX_METRICS} metrics per report.")
    if len(dimension_names) > API_MAX_DIMENSIONS:
        raise click.UsageError(f"At most {API_MAX_DIMENSIONS} dimensions per report.")
    prop = props.resolve(ctx)
    request = clients.data_types.RunRealtimeReportRequest(
        property=prop,
        metrics=[clients.data_types.Metric(name=name) for name in metric_names],
        dimensions=[clients.data_types.Dimension(name=name) for name in dimension_names],
        minute_ranges=[
            clients.data_types.MinuteRange(start_minutes_ago=minutes - 1, end_minutes_ago=0)
        ],
        limit=limit,
    )
    response = clients.get_data_client(ctx).run_realtime_report(
        request=request, timeout=ctx.obj["timeout"]
    )
    if raw:
        output.emit(type(response).to_dict(response), force_json=True)
        if fail_empty and not response.rows:
            sys.exit(EXIT_EMPTY)
        return
    rows = flatten.flatten_rows(response)
    row_count = int(response.row_count)
    envelope: dict[str, Any] = {
        "property": prop,
        "minutes": minutes,
        "rows": rows,
        "row_count": row_count,
        "returned": len(rows),
        "has_more": len(rows) < row_count,
    }
    output.emit(rows if results_only else envelope)
    if fail_empty and not rows:
        sys.exit(EXIT_EMPTY)
