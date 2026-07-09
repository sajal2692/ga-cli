from __future__ import annotations

import re
from typing import Any

import click
from google.api_core import exceptions as api_exceptions

from ga_cli import clients, output, props
from ga_cli.commands import global_options, split_csv
from ga_cli.commands.report import API_MAX_DIMENSIONS, API_MAX_METRICS
from ga_cli.errors import handle_errors


def _check(
    client: Any, prop: str, metric_names: list[str], dimension_names: list[str], timeout: float
) -> Any:
    return client.check_compatibility(
        request=clients.data_types.CheckCompatibilityRequest(
            property=prop,
            metrics=[clients.data_types.Metric(name=name) for name in metric_names],
            dimensions=[clients.data_types.Dimension(name=name) for name in dimension_names],
            compatibility_filter=clients.data_types.Compatibility.INCOMPATIBLE,
        ),
        timeout=timeout,
    )


def _attribute(
    client: Any, prop: str, metric_names: list[str], dimension_names: list[str], timeout: float
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    # The API rejects an already-incompatible request outright instead of
    # flagging fields, so blame each side against the other side alone.
    incompatible_metrics: list[dict[str, str]] = []
    incompatible_dimensions: list[dict[str, str]] = []
    if metric_names and dimension_names:
        try:
            response = _check(client, prop, [], dimension_names, timeout)
            candidates = {c.metric_metadata.api_name for c in response.metric_compatibilities}
            incompatible_metrics = [
                {"name": name, "reason": "INCOMPATIBLE"}
                for name in metric_names
                if name in candidates
            ]
        except api_exceptions.InvalidArgument:
            pass
        try:
            response = _check(client, prop, metric_names, [], timeout)
            candidates = {c.dimension_metadata.api_name for c in response.dimension_compatibilities}
            incompatible_dimensions = [
                {"name": name, "reason": "INCOMPATIBLE"}
                for name in dimension_names
                if name in candidates
            ]
        except api_exceptions.InvalidArgument:
            pass
    return incompatible_metrics, incompatible_dimensions


@click.command("compat")
@click.option("-m", "--metrics", "metrics_csv", default="", help="Comma-separated metrics.")
@click.option("-d", "--dims", "dims_csv", default="", help="Comma-separated dimensions.")
@global_options
@click.pass_context
@handle_errors
def compat(ctx: click.Context, metrics_csv: str, dims_csv: str) -> None:
    """Check whether a metric and dimension combination is compatible."""
    metric_names = split_csv(metrics_csv)
    dimension_names = split_csv(dims_csv)
    if not metric_names and not dimension_names:
        raise click.UsageError("Provide --metrics and/or --dims to check.")
    if len(metric_names) > API_MAX_METRICS:
        raise click.UsageError(f"At most {API_MAX_METRICS} metrics per report.")
    if len(dimension_names) > API_MAX_DIMENSIONS:
        raise click.UsageError(f"At most {API_MAX_DIMENSIONS} dimensions per report.")
    prop = props.resolve(ctx)
    assert prop is not None
    client = clients.get_data_client(ctx)
    timeout = ctx.obj["timeout"]
    try:
        response = _check(client, prop, metric_names, dimension_names, timeout)
    except api_exceptions.InvalidArgument as exc:
        message = str(getattr(exc, "message", None) or exc)
        if not re.search(r"incompatib", message, re.IGNORECASE):
            raise
        incompatible_metrics, incompatible_dimensions = _attribute(
            client, prop, metric_names, dimension_names, timeout
        )
        output.emit(
            {
                "compatible": False,
                "incompatible_metrics": incompatible_metrics,
                "incompatible_dimensions": incompatible_dimensions,
            }
        )
        return
    requested_metrics = set(metric_names)
    requested_dimensions = set(dimension_names)
    incompatible_metrics = [
        {"name": item.metric_metadata.api_name, "reason": item.compatibility.name}
        for item in response.metric_compatibilities
        if item.metric_metadata.api_name in requested_metrics
    ]
    incompatible_dimensions = [
        {"name": item.dimension_metadata.api_name, "reason": item.compatibility.name}
        for item in response.dimension_compatibilities
        if item.dimension_metadata.api_name in requested_dimensions
    ]
    output.emit(
        {
            "compatible": not incompatible_metrics and not incompatible_dimensions,
            "incompatible_metrics": incompatible_metrics,
            "incompatible_dimensions": incompatible_dimensions,
        }
    )
