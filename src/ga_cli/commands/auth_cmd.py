from __future__ import annotations

from typing import Any

import click

from ga_cli import auth, clients, flatten, output, props
from ga_cli.commands import global_options
from ga_cli.errors import handle_errors

GUIDE = """\
Set up read-only Google Analytics 4 access for ga-cli:

1. Create or pick a Google Cloud project:
   https://console.cloud.google.com/projectcreate

2. Enable both Analytics APIs for that project:
   https://console.cloud.google.com/apis/library/analyticsdata.googleapis.com
   https://console.cloud.google.com/apis/library/analyticsadmin.googleapis.com

3. Create a service account and download a JSON key:
   https://console.cloud.google.com/iam-admin/serviceaccounts
   (Keys tab > Add key > Create new key > JSON)

4. In Google Analytics, grant the service account read access:
   Admin > Property access management > Add users
   Use the service account email (ends in .iam.gserviceaccount.com), role Viewer.

5. Save the key and point ga-cli at it:
   mkdir -p ~/.config/ga-cli
   mv ~/Downloads/<key>.json ~/.config/ga-cli/sa.json
   printf 'credentials = "~/.config/ga-cli/sa.json"\\ndefault_property = "properties/<id>"\\n' \\
     > ~/.config/ga-cli/config.toml
   (find the property ID with: ga4 properties)

6. Verify end to end:
   ga4 auth check --ping\
"""


@click.group("auth")
@global_options
def auth_group() -> None:
    """Check credentials or print setup steps."""


@auth_group.command("check")
@click.option("--ping", is_flag=True, help="Also run a 1-row report against the property.")
@global_options
@click.pass_context
@handle_errors
def auth_check(ctx: click.Context, ping: bool) -> None:
    """Verify the credential chain and API access."""
    info = auth.credentials_for_ctx(ctx)
    summaries = props.account_summaries(ctx)
    accessible = sum(len(summary.property_summaries) for summary in summaries)
    result: dict[str, Any] = {"ok": True, "credentials_source": info.source}
    if info.path:
        result["credentials_path"] = info.path
    if info.principal:
        result["principal"] = info.principal
    result["type"] = info.type
    result["accessible_properties"] = accessible
    prop = props.resolve(ctx, required=False)
    if prop:
        result["default_property"] = prop
    if ping:
        prop = props.resolve(ctx)
        response = clients.get_data_client(ctx).run_report(
            request=clients.data_types.RunReportRequest(
                property=prop,
                metrics=[clients.data_types.Metric(name="activeUsers")],
                date_ranges=[clients.data_types.DateRange(start_date="today", end_date="today")],
                limit=1,
                return_property_quota=True,
            ),
            timeout=ctx.obj["timeout"],
        )
        result["ping_ok"] = True
        result["quota"] = flatten.quota_dict(response.property_quota)
    output.emit(result)


@auth_group.command("guide")
@global_options
@handle_errors
def auth_guide() -> None:
    """Print copy-pasteable setup steps."""
    click.echo(GUIDE)
