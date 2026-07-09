from __future__ import annotations

import click
from google.analytics import admin_v1beta
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta import types as data_types

from ga_cli import auth

__all__ = ["admin_v1beta", "data_types", "get_admin_client", "get_data_client"]


def get_data_client(ctx: click.Context) -> BetaAnalyticsDataClient:
    obj = ctx.obj
    if "_data_client" not in obj:
        info = auth.credentials_for_ctx(ctx)
        obj["_data_client"] = BetaAnalyticsDataClient(credentials=info.credentials)
    client: BetaAnalyticsDataClient = obj["_data_client"]
    return client


def get_admin_client(ctx: click.Context) -> admin_v1beta.AnalyticsAdminServiceClient:
    obj = ctx.obj
    if "_admin_client" not in obj:
        info = auth.credentials_for_ctx(ctx)
        obj["_admin_client"] = admin_v1beta.AnalyticsAdminServiceClient(
            credentials=info.credentials
        )
    client: admin_v1beta.AnalyticsAdminServiceClient = obj["_admin_client"]
    return client
