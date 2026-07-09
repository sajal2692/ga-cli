from __future__ import annotations

import sys
from typing import Any

import click
from click.core import ParameterSource

from ga_cli import clients, dates, filters, flatten, orders, output, props
from ga_cli.commands import RANGE_HELP, global_options, split_csv
from ga_cli.errors import EXIT_EMPTY, handle_errors

API_MAX_METRICS = 10
API_MAX_DIMENSIONS = 9
API_MAX_LIMIT = 250000
PAGE_LIMIT = 250000
MAX_ACCUMULATED_ROWS = 250000


def run_report_command(
    ctx: click.Context,
    *,
    metrics_csv: str,
    dims_csv: str,
    ranges: tuple[str, ...],
    compare: str | None,
    filter_exprs: tuple[str, ...],
    filter_any: tuple[str, ...],
    filter_json: str | None,
    case_sensitive: bool,
    order_specs: tuple[str, ...],
    limit: int,
    limit_explicit: bool,
    offset: int,
    fetch_all: bool,
    totals: bool,
    quota: bool,
    fail_empty: bool,
    results_only: bool,
    raw: bool,
) -> None:
    metric_names = split_csv(metrics_csv)
    dimension_names = split_csv(dims_csv)
    if not metric_names:
        raise click.UsageError("-m/--metrics requires at least one metric name.")
    if len(metric_names) > API_MAX_METRICS:
        raise click.UsageError(f"At most {API_MAX_METRICS} metrics per report.")
    if len(dimension_names) > API_MAX_DIMENSIONS:
        raise click.UsageError(f"At most {API_MAX_DIMENSIONS} dimensions per report.")
    if raw and fetch_all:
        raise click.UsageError("--raw cannot be combined with --all.")
    resolved_ranges = dates.parse_ranges(ranges, compare)
    dimension_filter, metric_filter = filters.build(
        filters=filter_exprs,
        filter_any=filter_any,
        filter_json=filter_json,
        metric_names=metric_names,
        case_sensitive=case_sensitive,
    )
    order_bys = orders.build(order_specs, metric_names, dimension_names)
    prop = props.resolve(ctx)

    request = clients.data_types.RunReportRequest(
        property=prop,
        date_ranges=[
            clients.data_types.DateRange(start_date=r.start, end_date=r.end, name=r.name)
            for r in resolved_ranges
        ],
        dimensions=[clients.data_types.Dimension(name=name) for name in dimension_names],
        metrics=[clients.data_types.Metric(name=name) for name in metric_names],
        limit=limit,
        offset=offset,
        return_property_quota=quota,
    )
    if dimension_filter is not None:
        request.dimension_filter = dimension_filter
    if metric_filter is not None:
        request.metric_filter = metric_filter
    if order_bys is not None:
        request.order_bys = order_bys
    if totals:
        request.metric_aggregations = [
            clients.data_types.MetricAggregation.TOTAL  # type: ignore[list-item]
        ]

    client = clients.get_data_client(ctx)
    timeout = ctx.obj["timeout"]

    if raw:
        response = client.run_report(request=request, timeout=timeout)
        output.emit(type(response).to_dict(response), force_json=True)
        if fail_empty and not response.rows:
            sys.exit(EXIT_EMPTY)
        return

    # The API counts limit/offset/row_count in base rows (unique dimension
    # combinations); with N date ranges each base row arrives as N response rows.
    num_ranges = len(resolved_ranges)
    rows, row_count, response = _fetch(
        client, request, timeout, fetch_all=fetch_all, limit=limit,
        limit_explicit=limit_explicit, offset=offset, num_ranges=num_ranges,
    )
    base_returned = len(rows) // num_ranges if num_ranges > 1 else len(rows)
    envelope: dict[str, Any] = {
        "property": prop,
        "date_ranges": [{"name": r.name, "start": r.start, "end": r.end} for r in resolved_ranges],
        "rows": rows,
        "row_count": row_count,
        "returned": len(rows),
        "has_more": offset + base_returned < row_count,
    }
    if totals:
        totals_value = flatten.flatten_totals(response)
        if totals_value is not None:
            envelope["totals"] = totals_value
    if quota and response.property_quota:
        envelope["quota"] = flatten.quota_dict(response.property_quota)
    output.emit(rows if results_only else envelope)
    if fail_empty and not rows:
        sys.exit(EXIT_EMPTY)


def _fetch(
    client: Any,
    request: Any,
    timeout: float,
    *,
    fetch_all: bool,
    limit: int,
    limit_explicit: bool,
    offset: int,
    num_ranges: int,
) -> tuple[list[dict[str, Any]], int, Any]:
    if not fetch_all:
        response = client.run_report(request=request, timeout=timeout)
        return flatten.flatten_rows(response), int(response.row_count), response
    page_limit = limit if limit_explicit else PAGE_LIMIT
    rows: list[dict[str, Any]] = []
    base_consumed = 0
    while True:
        request.limit = page_limit
        request.offset = offset + base_consumed
        response = client.run_report(request=request, timeout=timeout)
        page = flatten.flatten_rows(response)
        rows.extend(page)
        base_consumed += len(page) // num_ranges if num_ranges > 1 else len(page)
        row_count = int(response.row_count)
        if offset + base_consumed >= row_count:
            break
        if not page:
            click.echo("Warning: pagination stopped early (server returned no rows).", err=True)
            break
        if len(rows) >= MAX_ACCUMULATED_ROWS:
            remaining = row_count - offset - base_consumed
            click.echo(
                f"Warning: stopped after {MAX_ACCUMULATED_ROWS} accumulated rows; "
                f"{remaining} more rows match.",
                err=True,
            )
            break
    return rows, row_count, response


@click.command("report")
@click.option("-m", "--metrics", "metrics_csv", required=True,
              help="Comma-separated metrics (max 10).")
@click.option("-d", "--dims", "dims_csv", default="",
              help="Comma-separated dimensions (max 9).")
@click.option("-r", "--range", "ranges", multiple=True, help=RANGE_HELP + " Default: 28d.")
@click.option("--compare", type=click.Choice(["prev", "yoy"]),
              help="Add a computed comparison range.")
@click.option("-f", "--filter", "filter_exprs", multiple=True,
              help="Filter expression (repeatable, AND). Example: pagePath=^/blog")
@click.option("--filter-any", "filter_any", multiple=True,
              help="Filter expression joined into one OR group (repeatable).")
@click.option("--filter-json", "filter_json",
              help="Raw FilterExpression JSON, inline or @file.")
@click.option("--case-sensitive", is_flag=True, help="Match string filters case-sensitively.")
@click.option("-o", "--order", "order_specs", multiple=True,
              help="Order spec: field or -field (repeatable). Default: first metric desc. "
                   "'-o none' disables ordering.")
@click.option("--limit", type=click.IntRange(1, API_MAX_LIMIT), default=20, show_default=True,
              help="Max rows to return.")
@click.option("--offset", type=click.IntRange(min=0), default=0, help="Row offset.")
@click.option("--all", "fetch_all", is_flag=True,
              help="Auto-page until all rows are fetched (capped at 250000 rows).")
@click.option("--totals", is_flag=True, help="Include a totals object in the envelope.")
@click.option("--quota", "quota", is_flag=True, help="Include property quota in the envelope.")
@click.option("--fail-empty", is_flag=True, help="Exit 3 when zero rows.")
@click.option("--results-only", is_flag=True, help="Emit the bare rows array.")
@click.option("--raw", is_flag=True, help="Emit the raw API response without flattening.")
@global_options
@click.pass_context
@handle_errors
def report(
    ctx: click.Context,
    metrics_csv: str,
    dims_csv: str,
    ranges: tuple[str, ...],
    compare: str | None,
    filter_exprs: tuple[str, ...],
    filter_any: tuple[str, ...],
    filter_json: str | None,
    case_sensitive: bool,
    order_specs: tuple[str, ...],
    limit: int,
    offset: int,
    fetch_all: bool,
    totals: bool,
    quota: bool,
    fail_empty: bool,
    results_only: bool,
    raw: bool,
) -> None:
    """Run a GA4 report."""
    limit_explicit = ctx.get_parameter_source("limit") is not ParameterSource.DEFAULT
    run_report_command(
        ctx,
        metrics_csv=metrics_csv,
        dims_csv=dims_csv,
        ranges=ranges,
        compare=compare,
        filter_exprs=filter_exprs,
        filter_any=filter_any,
        filter_json=filter_json,
        case_sensitive=case_sensitive,
        order_specs=order_specs,
        limit=limit,
        limit_explicit=limit_explicit,
        offset=offset,
        fetch_all=fetch_all,
        totals=totals,
        quota=quota,
        fail_empty=fail_empty,
        results_only=results_only,
        raw=raw,
    )
