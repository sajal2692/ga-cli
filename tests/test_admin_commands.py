from __future__ import annotations

import datetime
import json
from typing import Any

from ga_cli.clients import admin_v1beta
from tests.conftest import FakeAdminClient, account_summary

ENV = {"GA_PROPERTY": "123456789"}


def test_accounts_golden(invoke: Any, fake_admin: FakeAdminClient, golden: Any) -> None:
    result = invoke("accounts")
    assert result.exit_code == 0
    golden(result, "accounts.json")
    name, request, timeout = fake_admin.calls[0]
    assert name == "list_account_summaries"
    assert timeout == 30.0


def test_accounts_omits_empty_properties(invoke: Any, fake_admin: FakeAdminClient) -> None:
    fake_admin.account_summaries = [account_summary("200", "Empty", [])]
    result = invoke("accounts")
    assert json.loads(result.stdout) == [{"account": "accounts/200", "display": "Empty"}]


def test_properties_list_golden(invoke: Any, fake_admin: FakeAdminClient, golden: Any) -> None:
    result = invoke("properties", "list")
    assert result.exit_code == 0
    golden(result, "properties_list.json")


def test_properties_bare_defaults_to_list(
    invoke: Any, fake_admin: FakeAdminClient, golden: Any
) -> None:
    result = invoke("properties")
    assert result.exit_code == 0
    golden(result, "properties_list.json")


def test_properties_get_golden(invoke: Any, fake_admin: FakeAdminClient, golden: Any) -> None:
    fake_admin.property = admin_v1beta.Property(
        name="properties/123456789",
        display_name="sajalsharma.com",
        time_zone="Asia/Singapore",
        currency_code="USD",
        industry_category=admin_v1beta.IndustryCategory.TECHNOLOGY,
        service_level=admin_v1beta.ServiceLevel.GOOGLE_ANALYTICS_STANDARD,
        create_time=datetime.datetime(2023, 4, 2, 9, 11, tzinfo=datetime.UTC),
    )
    result = invoke("properties", "get", "123456789")
    assert result.exit_code == 0
    golden(result, "properties_get.json")
    name, request, _ = fake_admin.calls[0]
    assert name == "get_property"
    assert request.name == "properties/123456789"


def test_properties_get_falls_back_to_chain(invoke: Any, fake_admin: FakeAdminClient) -> None:
    fake_admin.property = admin_v1beta.Property(
        name="properties/123456789", display_name="site"
    )
    result = invoke("properties", "get", env=ENV)
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data == {"id": "123456789", "property": "properties/123456789", "display": "site"}


def test_streams_golden(invoke: Any, fake_admin: FakeAdminClient, golden: Any) -> None:
    fake_admin.data_streams = [
        admin_v1beta.DataStream(
            name="properties/123456789/dataStreams/4567",
            type_=admin_v1beta.DataStream.DataStreamType.WEB_DATA_STREAM,
            display_name="Web",
            web_stream_data={
                "default_uri": "https://sajalsharma.com",
                "measurement_id": "G-ABC123",
            },
        ),
        admin_v1beta.DataStream(
            name="properties/123456789/dataStreams/999",
            type_=admin_v1beta.DataStream.DataStreamType.IOS_APP_DATA_STREAM,
            display_name="iOS",
            ios_app_stream_data={"bundle_id": "com.example.app"},
        ),
    ]
    result = invoke("streams", env=ENV)
    assert result.exit_code == 0
    golden(result, "streams.json")
    name, request, _ = fake_admin.calls[0]
    assert request.parent == "properties/123456789"


def test_custom_dimensions_golden(invoke: Any, fake_admin: FakeAdminClient, golden: Any) -> None:
    fake_admin.custom_dimensions = [
        admin_v1beta.CustomDimension(
            name="properties/123456789/customDimensions/1",
            parameter_name="author",
            display_name="Author",
            scope=admin_v1beta.CustomDimension.DimensionScope.EVENT,
        )
    ]
    result = invoke("custom-dimensions", env=ENV)
    assert result.exit_code == 0
    golden(result, "custom_dimensions.json")


def test_custom_metrics_golden(invoke: Any, fake_admin: FakeAdminClient, golden: Any) -> None:
    fake_admin.custom_metrics = [
        admin_v1beta.CustomMetric(
            name="properties/123456789/customMetrics/1",
            parameter_name="coins",
            display_name="Coins",
            scope=admin_v1beta.CustomMetric.MetricScope.EVENT,
            measurement_unit=admin_v1beta.CustomMetric.MeasurementUnit.STANDARD,
        )
    ]
    result = invoke("custom-metrics", env=ENV)
    assert result.exit_code == 0
    golden(result, "custom_metrics.json")


def test_key_events_golden(invoke: Any, fake_admin: FakeAdminClient, golden: Any) -> None:
    fake_admin.key_events = [
        admin_v1beta.KeyEvent(
            name="properties/123456789/keyEvents/9876",
            event_name="sign_up",
            counting_method=admin_v1beta.KeyEvent.CountingMethod.ONCE_PER_EVENT,
            custom=True,
        ),
        admin_v1beta.KeyEvent(
            name="properties/123456789/keyEvents/1111",
            event_name="purchase",
            counting_method=admin_v1beta.KeyEvent.CountingMethod.ONCE_PER_SESSION,
            custom=False,
        ),
    ]
    result = invoke("key-events", env=ENV)
    assert result.exit_code == 0
    golden(result, "key_events.json")


def test_property_auto_resolution_single(invoke: Any, fake_admin: FakeAdminClient) -> None:
    fake_admin.account_summaries = [
        account_summary("100", "Solo", [("properties/42", "only site")])
    ]
    fake_admin.data_streams = []
    result = invoke("streams")
    assert result.exit_code == 0
    assert "Using properties/42 (only accessible property)." in result.stderr
    assert json.loads(result.stdout) == []
    assert fake_admin.calls[-1][1].parent == "properties/42"


def test_no_property_usage_error(invoke: Any, fake_admin: FakeAdminClient) -> None:
    result = invoke("streams")
    assert result.exit_code == 2
    assert "No property specified" in result.stderr
    assert result.stdout == ""
