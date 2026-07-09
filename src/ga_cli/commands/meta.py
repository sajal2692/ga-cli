from __future__ import annotations

from typing import Any

import click

from ga_cli import clients, output, props
from ga_cli.commands import global_options
from ga_cli.errors import handle_errors


def _matches(item: Any, needle: str | None, custom_only: bool) -> bool:
    if custom_only and not item.custom_definition:
        return False
    if needle is None:
        return True
    return (
        needle in item.api_name.lower()
        or needle in item.ui_name.lower()
        or needle in item.description.lower()
    )


def _base_entry(item: Any, full: bool) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "name": item.api_name,
        "display": item.ui_name,
        "category": item.category,
    }
    if item.custom_definition:
        entry["custom"] = True
    if full and item.description:
        entry["description"] = item.description
    return entry


@click.command("meta")
@click.option("--search", default=None,
              help="Case-insensitive substring match on name, display, and description.")
@click.option("--type", "field_type", type=click.Choice(["dimensions", "metrics", "all"]),
              default="all", show_default=True, help="Restrict to one field kind.")
@click.option("--custom", "custom_only", is_flag=True, help="Only property-defined fields.")
@click.option("--full", is_flag=True, help="Include descriptions, types, and expressions.")
@global_options
@click.pass_context
@handle_errors
def meta(
    ctx: click.Context, search: str | None, field_type: str, custom_only: bool, full: bool
) -> None:
    """Discover valid metric and dimension names for the property."""
    prop = props.resolve(ctx)
    metadata = clients.get_data_client(ctx).get_metadata(
        request=clients.data_types.GetMetadataRequest(name=f"{prop}/metadata"),
        timeout=ctx.obj["timeout"],
    )
    needle = search.lower() if search else None
    dimensions: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []
    if field_type in ("dimensions", "all"):
        for item in metadata.dimensions:
            if _matches(item, needle, custom_only):
                dimensions.append(_base_entry(item, full))
    if field_type in ("metrics", "all"):
        for item in metadata.metrics:
            if not _matches(item, needle, custom_only):
                continue
            entry = _base_entry(item, full)
            if full:
                if item.type_:
                    entry["type"] = item.type_.name
                if item.expression:
                    entry["expression"] = item.expression
            metrics.append(entry)
    output.emit({"dimensions": dimensions, "metrics": metrics})
