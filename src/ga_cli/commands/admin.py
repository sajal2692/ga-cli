from __future__ import annotations

from typing import Any

import click

from ga_cli import clients, output, props
from ga_cli.commands import global_options
from ga_cli.errors import handle_errors


def _list(ctx: click.Context, method_name: str, request_cls: Any) -> Any:
    prop = props.resolve(ctx)
    client = clients.get_admin_client(ctx)
    method = getattr(client, method_name)
    return method(request=request_cls(parent=prop, page_size=200), timeout=ctx.obj["timeout"])


@click.command("streams")
@global_options
@click.pass_context
@handle_errors
def streams(ctx: click.Context) -> None:
    """List data streams for the property."""
    result = []
    pager = _list(ctx, "list_data_streams", clients.admin_v1beta.ListDataStreamsRequest)
    for stream in pager:
        entry: dict[str, Any] = {
            "id": stream.name.split("/")[-1],
            "stream": stream.name,
            "type": stream.type_.name,
        }
        if stream.display_name:
            entry["display"] = stream.display_name
        if "web_stream_data" in stream:
            data = stream.web_stream_data
            if data.default_uri:
                entry["uri"] = data.default_uri
            if data.measurement_id:
                entry["measurement_id"] = data.measurement_id
        elif "android_app_stream_data" in stream:
            if stream.android_app_stream_data.package_name:
                entry["package_name"] = stream.android_app_stream_data.package_name
        elif "ios_app_stream_data" in stream:
            if stream.ios_app_stream_data.bundle_id:
                entry["bundle_id"] = stream.ios_app_stream_data.bundle_id
        result.append(entry)
    output.emit(result)


@click.command("custom-dimensions")
@global_options
@click.pass_context
@handle_errors
def custom_dimensions(ctx: click.Context) -> None:
    """List custom dimensions for the property."""
    pager = _list(ctx, "list_custom_dimensions", clients.admin_v1beta.ListCustomDimensionsRequest)
    result = [
        {
            "parameter": item.parameter_name,
            "display": item.display_name,
            "scope": item.scope.name,
        }
        for item in pager
    ]
    output.emit(result)


@click.command("custom-metrics")
@global_options
@click.pass_context
@handle_errors
def custom_metrics(ctx: click.Context) -> None:
    """List custom metrics for the property."""
    result = []
    pager = _list(ctx, "list_custom_metrics", clients.admin_v1beta.ListCustomMetricsRequest)
    for item in pager:
        entry: dict[str, Any] = {
            "parameter": item.parameter_name,
            "display": item.display_name,
            "scope": item.scope.name,
        }
        if item.measurement_unit:
            entry["unit"] = item.measurement_unit.name
        result.append(entry)
    output.emit(result)


@click.command("key-events")
@global_options
@click.pass_context
@handle_errors
def key_events(ctx: click.Context) -> None:
    """List key events for the property."""
    result = []
    pager = _list(ctx, "list_key_events", clients.admin_v1beta.ListKeyEventsRequest)
    for item in pager:
        entry: dict[str, Any] = {
            "id": item.name.split("/")[-1],
            "event_name": item.event_name,
            "counting_method": item.counting_method.name,
        }
        if item.custom:
            entry["custom"] = True
        result.append(entry)
    output.emit(result)
