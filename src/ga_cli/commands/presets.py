from __future__ import annotations

import click

from ga_cli.commands import RANGE_HELP, global_options
from ga_cli.commands.report import API_MAX_LIMIT, run_report_command
from ga_cli.errors import handle_errors


def _make_preset(
    name: str,
    help_text: str,
    dimensions: list[str],
    metrics: list[str],
    order: tuple[str, ...],
) -> click.Command:
    equivalent = (
        f"ga4 report -m {','.join(metrics)} -d {','.join(dimensions)} "
        + " ".join(f"-o {spec}" for spec in order)
    )

    @click.command(name, help=help_text, epilog=f"Equivalent: {equivalent}")
    @click.option("-r", "--range", "ranges", multiple=True, help=RANGE_HELP + " Default: 28d.")
    @click.option("--limit", type=click.IntRange(1, API_MAX_LIMIT), default=10, show_default=True,
                  help="Max rows to return.")
    @click.option("-f", "--filter", "filter_exprs", multiple=True,
                  help="Filter expression (repeatable, AND). Example: pagePath=^/blog")
    @click.option("--compare", type=click.Choice(["prev", "yoy"]),
                  help="Add a computed comparison range.")
    @click.option("--fail-empty", is_flag=True, help="Exit 3 when zero rows.")
    @click.option("--results-only", is_flag=True, help="Emit the bare rows array.")
    @global_options
    @click.pass_context
    @handle_errors
    def preset(
        ctx: click.Context,
        ranges: tuple[str, ...],
        limit: int,
        filter_exprs: tuple[str, ...],
        compare: str | None,
        fail_empty: bool,
        results_only: bool,
    ) -> None:
        run_report_command(
            ctx,
            metrics_csv=",".join(metrics),
            dims_csv=",".join(dimensions),
            ranges=ranges,
            compare=compare,
            filter_exprs=filter_exprs,
            filter_any=(),
            filter_json=None,
            case_sensitive=False,
            order_specs=order,
            limit=limit,
            limit_explicit=True,
            offset=0,
            fetch_all=False,
            totals=False,
            quota=False,
            fail_empty=fail_empty,
            results_only=results_only,
            raw=False,
        )

    return preset


pages = _make_preset(
    "pages",
    "Top pages by views.",
    ["pagePath"],
    ["screenPageViews", "activeUsers"],
    ("-screenPageViews",),
)
sources = _make_preset(
    "sources",
    "Traffic by default channel group.",
    ["sessionDefaultChannelGroup"],
    ["sessions", "activeUsers"],
    ("-sessions",),
)
events = _make_preset(
    "events",
    "Top events by count.",
    ["eventName"],
    ["eventCount", "activeUsers"],
    ("-eventCount",),
)
trend = _make_preset(
    "trend",
    "Daily traffic trend.",
    ["date"],
    ["activeUsers", "sessions", "screenPageViews"],
    ("date",),
)
