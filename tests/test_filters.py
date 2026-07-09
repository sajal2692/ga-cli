from __future__ import annotations

import json
from pathlib import Path

import click
import pytest

from ga_cli import filters
from ga_cli.clients import data_types

MatchType = data_types.Filter.StringFilter.MatchType
Operation = data_types.Filter.NumericFilter.Operation


def build(
    exprs: tuple[str, ...] = (),
    any_exprs: tuple[str, ...] = (),
    filter_json: str | None = None,
    metrics: list[str] | None = None,
    case_sensitive: bool = False,
) -> tuple:
    return filters.build(
        filters=exprs,
        filter_any=any_exprs,
        filter_json=filter_json,
        metric_names=metrics or ["sessions", "activeUsers"],
        case_sensitive=case_sensitive,
    )


def test_prefix_filter() -> None:
    dim, metric = build(("pagePath=^/blog",))
    assert metric is None
    assert dim.filter.field_name == "pagePath"
    assert dim.filter.string_filter.match_type == MatchType.BEGINS_WITH
    assert dim.filter.string_filter.value == "/blog"
    assert dim.filter.string_filter.case_sensitive is False


@pytest.mark.parametrize(
    ("expr", "match_type"),
    [
        ("x=@mid", MatchType.CONTAINS),
        ("x=$end", MatchType.ENDS_WITH),
        ("x=~^a.*b$", MatchType.FULL_REGEXP),
    ],
)
def test_string_ops(expr: str, match_type: MatchType) -> None:
    dim, _ = build((expr,))
    assert dim.filter.string_filter.match_type == match_type


def test_negated_string_ops() -> None:
    dim, _ = build(("x!@spam",))
    inner = dim.not_expression.filter
    assert inner.string_filter.match_type == MatchType.CONTAINS
    assert inner.string_filter.value == "spam"
    dim, _ = build(("x!~^a$",))
    assert dim.not_expression.filter.string_filter.match_type == MatchType.FULL_REGEXP


def test_exact_and_in_list() -> None:
    dim, _ = build(("country==Singapore",))
    assert dim.filter.string_filter.match_type == MatchType.EXACT
    dim, _ = build(("country==United States|Canada|Singapore",))
    assert list(dim.filter.in_list_filter.values) == ["United States", "Canada", "Singapore"]
    dim, _ = build(("q==a\\|b",))
    assert dim.filter.string_filter.value == "a|b"


def test_not_equals_dimension() -> None:
    dim, _ = build(("country!=Singapore",))
    assert dim.not_expression.filter.string_filter.match_type == MatchType.EXACT
    dim, _ = build(("country!=a|b",))
    assert list(dim.not_expression.filter.in_list_filter.values) == ["a", "b"]


def test_case_sensitive_flag() -> None:
    dim, _ = build(("pagePath=^/Blog",), case_sensitive=True)
    assert dim.filter.string_filter.case_sensitive is True


def test_metric_filters() -> None:
    _, metric = build(("sessions>100",))
    assert metric.filter.field_name == "sessions"
    assert metric.filter.numeric_filter.operation == Operation.GREATER_THAN
    assert metric.filter.numeric_filter.value.int64_value == 100
    _, metric = build(("sessions==1.5",))
    assert metric.filter.numeric_filter.operation == Operation.EQUAL
    assert metric.filter.numeric_filter.value.double_value == 1.5
    _, metric = build(("sessions!=0",))
    assert metric.not_expression.filter.numeric_filter.operation == Operation.EQUAL


def test_numeric_op_on_dimension() -> None:
    dim, metric = build(("nthDay>5",))
    assert metric is None
    assert dim.filter.numeric_filter.operation == Operation.GREATER_THAN


def test_and_combination_and_partition() -> None:
    dim, metric = build(("pagePath=^/blog", "country==SG", "sessions>10"))
    assert len(dim.and_group.expressions) == 2
    assert metric.filter.field_name == "sessions"


def test_filter_any_or_group() -> None:
    dim, _ = build(("pagePath=^/blog",), any_exprs=("source=@github", "source=@linkedin"))
    assert len(dim.and_group.expressions) == 2
    or_group = dim.and_group.expressions[1].or_group
    assert len(or_group.expressions) == 2


def test_filter_any_alone() -> None:
    dim, _ = build(any_exprs=("source=@github", "source=@linkedin"))
    assert len(dim.or_group.expressions) == 2


def test_filter_any_mixed_kinds_rejected() -> None:
    with pytest.raises(click.UsageError):
        build(any_exprs=("source=@github", "sessions>10"))


@pytest.mark.parametrize(
    "expr",
    ["nonsense", "sessions=@x", "sessions>abc", "nthDay>abc", "pagePath=^", "==x"],
)
def test_invalid_expressions(expr: str) -> None:
    with pytest.raises(click.UsageError):
        build((expr,))


def test_filter_json_inline_and_wrapped() -> None:
    payload = {"filter": {"fieldName": "pagePath", "stringFilter": {"value": "/a"}}}
    dim, metric = build(filter_json=json.dumps(payload))
    assert dim.filter.field_name == "pagePath"
    assert metric is None
    wrapped = {"metric": {"filter": {"fieldName": "sessions", "numericFilter": {
        "operation": "GREATER_THAN", "value": {"int64Value": "5"}}}}}
    dim, metric = build(filter_json=json.dumps(wrapped))
    assert dim is None
    assert metric.filter.field_name == "sessions"


def test_filter_json_from_file(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    path.write_text('{"filter": {"field_name": "x", "string_filter": {"value": "y"}}}')
    dim, _ = build(filter_json=f"@{path}")
    assert dim.filter.field_name == "x"


def test_filter_json_errors(tmp_path: Path) -> None:
    with pytest.raises(click.UsageError):
        build(filter_json="not json")
    with pytest.raises(click.UsageError):
        build(filter_json='{"filter": {"bogusField": 1}}')
    with pytest.raises(click.UsageError):
        build(filter_json=f"@{tmp_path / 'missing.json'}")
    with pytest.raises(click.UsageError):
        build(("pagePath=^/a",), filter_json='{"filter": {}}')
