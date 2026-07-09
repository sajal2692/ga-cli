from __future__ import annotations

import re
from typing import Any

from ga_cli.clients import data_types

INT_TYPES = {data_types.MetricType.TYPE_INTEGER}
FLOAT_TYPES = {
    data_types.MetricType.TYPE_FLOAT,
    data_types.MetricType.TYPE_SECONDS,
    data_types.MetricType.TYPE_MILLISECONDS,
    data_types.MetricType.TYPE_MINUTES,
    data_types.MetricType.TYPE_HOURS,
    data_types.MetricType.TYPE_CURRENCY,
    data_types.MetricType.TYPE_FEET,
    data_types.MetricType.TYPE_MILES,
    data_types.MetricType.TYPE_METERS,
    data_types.MetricType.TYPE_KILOMETERS,
}


def coerce_metric(value: str, metric_type: Any) -> Any:
    if metric_type in INT_TYPES:
        try:
            return int(value)
        except ValueError:
            return value
    if metric_type in FLOAT_TYPES:
        try:
            return float(value)
        except ValueError:
            return value
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def normalize_dim(name: str, value: str) -> str:
    if name in ("date", "firstSessionDate") and re.match(r"^\d{8}$", value):
        return f"{value[0:4]}-{value[4:6]}-{value[6:8]}"
    if name == "dateHour" and re.match(r"^\d{10}$", value):
        return f"{value[0:4]}-{value[4:6]}-{value[6:8]}T{value[8:10]}"
    if name == "dateHourMinute" and re.match(r"^\d{12}$", value):
        return f"{value[0:4]}-{value[4:6]}-{value[6:8]}T{value[8:10]}:{value[10:12]}"
    if name == "yearMonth" and re.match(r"^\d{6}$", value):
        return f"{value[0:4]}-{value[4:6]}"
    if name == "yearWeek" and re.match(r"^\d{6}$", value):
        return f"{value[0:4]}-W{value[4:6]}"
    return value


def _emitted_name(header_name: str) -> str:
    return "date_range" if header_name == "dateRange" else header_name


def flatten_rows(response: Any) -> list[dict[str, Any]]:
    dimension_headers = [header.name for header in response.dimension_headers]
    metric_headers = [(header.name, header.type_) for header in response.metric_headers]
    rows: list[dict[str, Any]] = []
    for row in response.rows:
        flat: dict[str, Any] = {}
        for index, name in enumerate(dimension_headers):
            value = row.dimension_values[index].value
            if name == "dateRange":
                flat[_emitted_name(name)] = value
            else:
                flat[name] = normalize_dim(name, value)
        for index, (name, metric_type) in enumerate(metric_headers):
            flat[name] = coerce_metric(row.metric_values[index].value, metric_type)
        rows.append(flat)
    return rows


def flatten_totals(response: Any) -> Any:
    dimension_headers = [header.name for header in response.dimension_headers]
    metric_headers = [(header.name, header.type_) for header in response.metric_headers]
    totals: list[dict[str, Any]] = []
    for row in response.totals:
        flat: dict[str, Any] = {}
        for index, name in enumerate(dimension_headers):
            if name == "dateRange":
                flat["date_range"] = row.dimension_values[index].value
        for index, (name, metric_type) in enumerate(metric_headers):
            flat[name] = coerce_metric(row.metric_values[index].value, metric_type)
        totals.append(flat)
    if not totals:
        return None
    if len(totals) == 1:
        totals[0].pop("date_range", None)
        return totals[0]
    return totals


def quota_dict(property_quota: Any) -> dict[str, Any]:
    return {
        "tokens_per_day": {
            "consumed": property_quota.tokens_per_day.consumed,
            "remaining": property_quota.tokens_per_day.remaining,
        },
        "tokens_per_hour": {
            "consumed": property_quota.tokens_per_hour.consumed,
            "remaining": property_quota.tokens_per_hour.remaining,
        },
        "concurrent_requests": {
            "consumed": property_quota.concurrent_requests.consumed,
            "remaining": property_quota.concurrent_requests.remaining,
        },
    }
