from __future__ import annotations

from typing import Any

import click

from ga_cli.clients import data_types


def build(
    specs: tuple[str, ...], metric_names: list[str], dimension_names: list[str]
) -> list[Any] | None:
    if not specs:
        return [
            data_types.OrderBy(
                metric=data_types.OrderBy.MetricOrderBy(metric_name=metric_names[0]), desc=True
            )
        ]
    if "none" in specs:
        if len(specs) > 1:
            raise click.UsageError("-o none cannot be combined with other order specs.")
        return None
    order_bys: list[Any] = []
    for spec in specs:
        desc = spec.startswith("-")
        field = spec[1:] if desc else spec
        if field in metric_names:
            order_bys.append(
                data_types.OrderBy(
                    metric=data_types.OrderBy.MetricOrderBy(metric_name=field), desc=desc
                )
            )
        elif field in dimension_names:
            order_bys.append(
                data_types.OrderBy(
                    dimension=data_types.OrderBy.DimensionOrderBy(dimension_name=field), desc=desc
                )
            )
        else:
            raise click.UsageError(
                f"Order field '{field}' must be one of the requested metrics or dimensions."
            )
    return order_bys
