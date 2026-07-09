from __future__ import annotations

import json
import os
import sys
from typing import Any

import click
from rich.console import Console
from rich.table import Table


def emit(data: Any, *, force_json: bool = False) -> None:
    ctx = click.get_current_context()
    obj = ctx.obj
    if not force_json and _use_table(obj):
        _print_table(data)
    else:
        _print_json(data, compact=bool(obj.get("compact")))


def _use_table(obj: dict[str, Any]) -> bool:
    if obj.get("table"):
        return True
    if obj.get("compact"):
        return False
    return os.environ.get("GA_AUTO_TABLE") == "1" and sys.stdout.isatty()


def _print_json(data: Any, *, compact: bool) -> None:
    if compact:
        text = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    else:
        text = json.dumps(data, indent=2, ensure_ascii=False)
    click.echo(text)


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    return str(value)


def _rows_table(rows: list[dict[str, Any]]) -> Table:
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    table = Table(show_header=True, header_style="bold")
    for column in columns:
        table.add_column(column)
    for row in rows:
        table.add_row(*(_cell(row.get(column)) for column in columns))
    return table


def _print_table(data: Any) -> None:
    console = Console()
    if isinstance(data, dict) and isinstance(data.get("rows"), list):
        rows = data["rows"]
        if not rows:
            click.echo("No rows returned.", err=True)
            return
        console.print(_rows_table(rows))
        meta = {k: v for k, v in data.items() if k != "rows" and not isinstance(v, (dict, list))}
        summary = " | ".join(f"{k}={v}" for k, v in meta.items())
        if summary:
            click.echo(summary, err=True)
        return
    if isinstance(data, dict) and set(data) == {"dimensions", "metrics"}:
        rows = [{"kind": "dimension", **entry} for entry in data["dimensions"]]
        rows += [{"kind": "metric", **entry} for entry in data["metrics"]]
        if not rows:
            click.echo("No fields matched.", err=True)
            return
        console.print(_rows_table(rows))
        return
    if isinstance(data, list):
        if not data:
            click.echo("No results.", err=True)
            return
        rows = [row if isinstance(row, dict) else {"value": row} for row in data]
        console.print(_rows_table(rows))
        return
    if isinstance(data, dict):
        table = Table(show_header=False)
        table.add_column("key", style="bold")
        table.add_column("value")
        for key, value in data.items():
            table.add_row(key, _cell(value))
        console.print(table)
        return
    click.echo(_cell(data))
