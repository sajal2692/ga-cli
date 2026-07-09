from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import click
from google.protobuf import json_format

from ga_cli.clients import data_types

EXPR_RE = re.compile(r"^([A-Za-z0-9_:]+)(==|!=|=@|!@|=\^|=\$|=~|!~|>=|<=|>|<)(.+)$", re.DOTALL)

STRING_OPS = {
    "=@": (data_types.Filter.StringFilter.MatchType.CONTAINS, False),
    "!@": (data_types.Filter.StringFilter.MatchType.CONTAINS, True),
    "=^": (data_types.Filter.StringFilter.MatchType.BEGINS_WITH, False),
    "=$": (data_types.Filter.StringFilter.MatchType.ENDS_WITH, False),
    "=~": (data_types.Filter.StringFilter.MatchType.FULL_REGEXP, False),
    "!~": (data_types.Filter.StringFilter.MatchType.FULL_REGEXP, True),
}

NUMERIC_OPS = {
    "==": data_types.Filter.NumericFilter.Operation.EQUAL,
    ">": data_types.Filter.NumericFilter.Operation.GREATER_THAN,
    ">=": data_types.Filter.NumericFilter.Operation.GREATER_THAN_OR_EQUAL,
    "<": data_types.Filter.NumericFilter.Operation.LESS_THAN,
    "<=": data_types.Filter.NumericFilter.Operation.LESS_THAN_OR_EQUAL,
}

METRIC_OPS = ("==", "!=", ">", ">=", "<", "<=")

DSL_FORMS = "Expected FIELD OP VALUE with OP one of: == != =@ !@ =^ =$ =~ !~ > >= < <="


def _split_values(value: str) -> list[str]:
    parts = re.split(r"(?<!\\)\|", value)
    return [part.replace("\\|", "|") for part in parts]


def _numeric_value(value: str, expr: str) -> Any:
    try:
        return data_types.NumericValue(int64_value=int(value))
    except ValueError:
        pass
    try:
        return data_types.NumericValue(double_value=float(value))
    except ValueError:
        raise click.UsageError(
            f"Invalid filter '{expr}': numeric comparison requires a numeric value."
        ) from None


def _negate(expression: Any) -> Any:
    return data_types.FilterExpression(not_expression=expression)


def _string_expression(
    field: str, op: str, value: str, case_sensitive: bool, expr: str
) -> Any:
    values = _split_values(value)
    if op in ("==", "!="):
        if len(values) > 1:
            filt = data_types.Filter(
                field_name=field,
                in_list_filter=data_types.Filter.InListFilter(
                    values=values, case_sensitive=case_sensitive
                ),
            )
        else:
            filt = data_types.Filter(
                field_name=field,
                string_filter=data_types.Filter.StringFilter(
                    match_type=data_types.Filter.StringFilter.MatchType.EXACT,
                    value=values[0],
                    case_sensitive=case_sensitive,
                ),
            )
        expression = data_types.FilterExpression(filter=filt)
        return _negate(expression) if op == "!=" else expression
    match_type, negated = STRING_OPS[op]
    expression = data_types.FilterExpression(
        filter=data_types.Filter(
            field_name=field,
            string_filter=data_types.Filter.StringFilter(
                match_type=match_type,
                value=value.replace("\\|", "|"),
                case_sensitive=case_sensitive,
            ),
        )
    )
    return _negate(expression) if negated else expression


def _numeric_expression(field: str, op: str, value: str, expr: str) -> Any:
    numeric = _numeric_value(value, expr)
    if op == "!=":
        equal = data_types.FilterExpression(
            filter=data_types.Filter(
                field_name=field,
                numeric_filter=data_types.Filter.NumericFilter(
                    operation=data_types.Filter.NumericFilter.Operation.EQUAL, value=numeric
                ),
            )
        )
        return _negate(equal)
    return data_types.FilterExpression(
        filter=data_types.Filter(
            field_name=field,
            numeric_filter=data_types.Filter.NumericFilter(
                operation=NUMERIC_OPS[op], value=numeric
            ),
        )
    )


def parse_expr(
    expr: str, metric_names: list[str], case_sensitive: bool
) -> tuple[Any, bool]:
    match = EXPR_RE.match(expr)
    if not match:
        if re.match(r"^[A-Za-z0-9_:]+(==|!=|=@|!@|=\^|=\$|=~|!~|>=|<=|>|<)$", expr):
            raise click.UsageError(
                f"Invalid filter '{expr}': empty values are not expressible in the DSL; "
                "use --filter-json."
            )
        raise click.UsageError(f"Invalid filter '{expr}'. {DSL_FORMS}.")
    field, op, value = match.groups()
    is_metric = field in metric_names
    if is_metric:
        if op not in METRIC_OPS:
            raise click.UsageError(
                f"Invalid filter '{expr}': operator '{op}' is not valid for metric "
                f"'{field}'. Metrics support: {' '.join(METRIC_OPS)}."
            )
        return _numeric_expression(field, op, value, expr), True
    if op in NUMERIC_OPS and op != "==":
        return _numeric_expression(field, op, value, expr), False
    return _string_expression(field, op, value, case_sensitive, expr), False


def _combine(expressions: list[Any]) -> Any:
    if not expressions:
        return None
    if len(expressions) == 1:
        return expressions[0]
    return data_types.FilterExpression(
        and_group=data_types.FilterExpressionList(expressions=expressions)
    )


def _load_filter_json(raw: str) -> dict[str, Any]:
    text = raw
    if raw.startswith("@"):
        path = Path(raw[1:]).expanduser()
        if not path.is_file():
            raise click.UsageError(f"Filter JSON file not found: {path}")
        text = path.read_text()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise click.UsageError(f"Invalid --filter-json: {exc}") from None
    if not isinstance(payload, dict):
        raise click.UsageError("Invalid --filter-json: expected a JSON object.")
    return payload


def _expression_from_dict(payload: dict[str, Any]) -> Any:
    expression = data_types.FilterExpression()
    try:
        json_format.ParseDict(payload, data_types.FilterExpression.pb(expression))
    except json_format.ParseError as exc:
        raise click.UsageError(f"Invalid --filter-json FilterExpression: {exc}") from None
    return expression


def build(
    *,
    filters: tuple[str, ...],
    filter_any: tuple[str, ...],
    filter_json: str | None,
    metric_names: list[str],
    case_sensitive: bool,
) -> tuple[Any, Any]:
    if filter_json and (filters or filter_any):
        raise click.UsageError("--filter-json cannot be combined with -f/--filter or --filter-any.")
    if filter_json:
        payload = _load_filter_json(filter_json)
        keys = set(payload)
        if keys and keys <= {"metric", "dimension"}:
            metric_expr = _expression_from_dict(payload["metric"]) if "metric" in payload else None
            dimension_expr = (
                _expression_from_dict(payload["dimension"]) if "dimension" in payload else None
            )
            return dimension_expr, metric_expr
        return _expression_from_dict(payload), None

    dimension_parts: list[Any] = []
    metric_parts: list[Any] = []
    for expr in filters:
        expression, is_metric = parse_expr(expr, metric_names, case_sensitive)
        (metric_parts if is_metric else dimension_parts).append(expression)

    if filter_any:
        parsed = [parse_expr(expr, metric_names, case_sensitive) for expr in filter_any]
        kinds = {is_metric for _, is_metric in parsed}
        if len(kinds) > 1:
            raise click.UsageError(
                "--filter-any cannot mix metric and dimension fields in one OR group."
            )
        group = data_types.FilterExpression(
            or_group=data_types.FilterExpressionList(
                expressions=[expression for expression, _ in parsed]
            )
        )
        (metric_parts if kinds.pop() else dimension_parts).append(group)

    return _combine(dimension_parts), _combine(metric_parts)
