# ga-cli Specification

Agent-native command-line interface for Google Analytics 4, built on Google's official Python client libraries.

- Status: approved for implementation, targeting a public v1.0.0 release
- Location: `~/code/active/tools/ga-cli` | Public repo (at release): `github.com/sajal2692/ga-cli`
- Date: 2026-07-09
- Binary: `ga` | Package: `ga_cli` | Distribution: `ga-cli` (unclaimed on PyPI as of 2026-07-09)

> **As shipped (v1.0.1):** two names in this spec were unavailable in practice.
> The **PyPI distribution is `ga-agent-cli`** (`ga-cli` is blocked as confusable
> with the existing `gacli`), and the **command is `ga4`** (`ga` collides with the
> oh-my-zsh git plugin's `ga='git add'` alias). The import package (`ga_cli`), repo
> (`sajal2692/ga-cli`), config dir (`~/.config/ga-cli`), and skill (`ga-cli`) are
> unchanged. The rest of this document reflects the original design.

## Bootstrap notes for the implementing session

Read this spec fully before writing code. Additional context:

- Style references on this machine: `~/code/active/tools/ynab-cli` (primary; src layout, Click, JSON-default output) and `~/code/active/tools/hevy-cli` (skill packaging layout). Match their code style: plain Click commands, small modules, minimal comments, no emojis anywhere.
- Design lineage: steipete's `gogcli` and `goplaces` (Go CLIs designed for agents). Clone them if a convention question comes up that this spec does not answer: `https://github.com/steipete/gogcli`, `https://github.com/steipete/goplaces`.
- This tool is a superset of `gog analytics` (which offers only `accounts` and a basic `report`). Parity checklist in Appendix A.
- Everything in this spec is v1 scope unless marked "Deferred".

## 1. Purpose

Give AI agents (Claude Code via a skill, primarily) and humans first-class terminal access to GA4 reporting and property metadata. One binary, task-first commands, JSON that agents can consume without reshaping, stable exit codes for branching, and zero interactive prompts.

Read-only by construction: only read methods of the GA4 APIs are ever bound. There is no mutation path to guard against.

### Why not existing tools

| Tool | Gap |
|---|---|
| `gog analytics` (gogcli) | Only `accounts` + basic `report`. Single date range, no filters, no ordering, no realtime, no field discovery, no admin listers, raw unflattened row output, property ID required on every call. |
| `googleanalytics/google-analytics-mcp` | MCP server, not a CLI. Tool schemas occupy context; not composable with shell pipelines. |
| `Bin-Huang/google-analytics-cli` | Node, young, raw API passthrough output. |
| `ga4-cli` (PyPI, unrelated) | Property management focus, not agent-oriented reporting. |

## 2. Design principles

Distilled from gogcli, goplaces, and the user's own tools. In priority order when principles conflict:

1. Correct, secure API behavior.
2. Stable automation contracts: command names, flags, env vars, exit codes, and JSON field names are compatibility surfaces. They freeze at v1.0.0; breaking any of them afterward is a major-version event and must be changelogged.
3. Clear errors with the exact remediation command in the message.
4. Token-frugal output: lean fields, small default limits, flattened rows.
5. Pleasant human output (tables) as a secondary mode.

Operational rules:

- One surface for humans and agents. No separate agent mode.
- JSON on stdout is the default output. Data goes to stdout, everything else (progress, hints, warnings, errors) goes to stderr.
- Never prompt. There is no interactive input anywhere in v1, so no `--no-input` flag is needed; the tool must never block on a TTY read.
- Deterministic output: same inputs, same JSON shape. Optional fields are omitted when empty rather than emitted as null/empty.
- Small defaults, explicit maxima, client-side validation before any network call.

## 3. Naming, layout, distribution

### Names

- Repo/dir: `ga-cli`. Python import package: `ga_cli`. Console script: `ga`.
- PyPI distribution name `ga-cli` (verified unclaimed 2026-07-09). Publishing is deferred; install is local for now.
- Env var prefix: `GA_` (`GA_PROPERTY`, `GA_CREDENTIALS`, `GA_CONFIG`, `GA_AUTO_TABLE`).

### Repository layout

```
ga-cli/
  pyproject.toml
  README.md
  SPEC.md                      (this file)
  CHANGELOG.md
  uv.lock
  .github/workflows/
    ci.yml                     (lint + type + test on push/PR)
    release.yml                (tag -> build -> PyPI publish -> GitHub release)
  src/ga_cli/
    __init__.py                (__version__)
    cli.py                     (root Click group, global flags)
    config.py                  (config.toml load, path resolution)
    clients.py                 (client factories; the only module that imports google.analytics)
    auth.py                    (credential resolution chain)
    props.py                   (property resolution: flag > env > config > auto)
    output.py                  (JSON/table emitters, --results-only, --compact)
    errors.py                  (exception -> exit code mapping, remediation messages)
    dates.py                   (date range grammar parser)
    filters.py                 (filter DSL -> FilterExpression)
    orders.py                  (order grammar -> OrderBy)
    flatten.py                 (response -> lean rows)
    commands/
      __init__.py
      auth_cmd.py              (ga auth check|guide)
      accounts.py              (ga accounts)
      properties.py            (ga properties list|get)
      admin.py                 (ga streams|custom-dimensions|custom-metrics|key-events)
      meta.py                  (ga meta)
      compat.py                (ga compat)
      report.py                (ga report)
      realtime.py              (ga realtime)
      presets.py               (ga pages|sources|events|trend)
      quota.py                 (ga quota)
      skill_cmd.py             (ga skill install|show|path)
  skills/
    ga-cli/
      SKILL.md
      references/commands.md
  tests/
    conftest.py                (fake client fixtures)
    golden/                    (expected JSON outputs)
    test_*.py
```

### Build tooling

- `uv` managed. Build backend: hatchling. `requires-python = ">=3.11"`.
- The bundled skill is shipped as package data: hatch force-includes `skills/ga-cli/` into the wheel as `ga_cli/_skill/`, so `ga skill install` works from any install channel (Section 8.11).

### Install channels (document all four in README)

1. Local dev: `uv tool install --editable ~/code/active/tools/ga-cli`. Verify with `ga --version`.
2. PyPI (primary): `uv tool install ga-cli` (also works with `pipx install ga-cli` and plain `pip`).
3. Homebrew: `brew install sajal2692/tap/ga-cli`.
4. From source: `uv tool install git+https://github.com/sajal2692/ga-cli`.

### Homebrew tap

- Separate repo `github.com/sajal2692/homebrew-tap`, formula at `Formula/ga-cli.rb`.
- Formula style: `include Language::Python::Virtualenv`, `depends_on "python@3.13"`, `url` pointing at the PyPI sdist, resource blocks for all transitive deps generated with `brew update-python-resources ga-cli`, installed via `virtualenv_install_with_resources`.
- Known cost: the Google clients pull `grpcio`, which compiles slowly from sdist. If formula build time is unacceptable, the sanctioned fallback for a personal tap is a formula that creates a venv in `libexec` and installs the released wheel set with `uv pip install ga-cli==<version>` (`depends_on "uv"`). Try the standard virtualenv pattern first.
- Formula `caveats` must print: `Install the Claude Code skill with: ga skill install`.
- Per release: bump `url`/`sha256`, rerun `brew update-python-resources`, push to the tap. Automation of the bump is deferred.

### Release process (v1.0.0 target)

- Versioning: semver, single source of truth in `pyproject.toml` (`ga --version` reads package metadata). First public release is `1.0.0`; the automation contract in Section 2 is frozen from that tag.
- CI (`ci.yml`): ruff + mypy + pytest on push/PR, Python 3.11 and 3.13.
- Release (`release.yml`): on `v*` tag push: run CI checks, `uv build`, publish to PyPI via trusted publishing (OIDC, no long-lived token), create a GitHub release with the CHANGELOG entry.
- Release checklist (README `RELEASING` section or CHANGELOG header): update CHANGELOG, tag, verify PyPI install, update brew formula, `brew install` smoke test, verify `ga skill install` from the brew build.

### Dependencies

```toml
dependencies = [
    "click>=8.1",
    "rich>=13.0",
    "google-analytics-data>=0.23,<1.0",
    "google-analytics-admin>=0.30,<1.0",
]
```

No httpx (the Google clients carry their own transport). No pydantic (proto messages + dicts suffice). Dev deps: pytest, ruff, mypy.

Import discipline (important): use the pinned beta surfaces explicitly.

```python
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta import types as data_types
from google.analytics import admin_v1beta
```

Never import the unversioned `google.analytics.admin` top-level package; it re-exports the v1alpha surface, which churns. All admin calls go through `admin_v1beta.AnalyticsAdminServiceClient`.

`clients.py` exposes `get_data_client()` and `get_admin_client()` factories; commands never construct clients directly. Tests monkeypatch these two functions.

## 4. Auth and configuration

### Credential resolution chain

First match wins. Every command that touches the network runs this chain.

1. `--credentials PATH` global flag
2. `GA_CREDENTIALS` env var (path to service account JSON)
3. `credentials` key in config file
4. `GOOGLE_APPLICATION_CREDENTIALS` env var (standard Google convention)
5. Application Default Credentials (covers `gcloud auth application-default login` user credentials and workload identity)
6. Fail with exit 4 and the message: `No Google credentials found. Run "ga auth guide" for setup steps.`

Service account JSON is the recommended path (grant the SA email Viewer on the GA4 property). The file is passed to clients via `service_account.Credentials.from_service_account_file(path, scopes=[...])`. Scope is always `https://www.googleapis.com/auth/analytics.readonly`. Never request a broader scope.

Security: never print token material or the full contents of the credentials file. `ga auth check` prints the service account email (from the JSON `client_email` field) and the source of the credentials, nothing else from the file.

### Config file

Path: `--config PATH` > `GA_CONFIG` > `~/.config/ga-cli/config.toml`. Missing file is fine; all keys optional.

```toml
default_property = "properties/123456789"
credentials = "~/.config/ga-cli/sa.json"

[properties]
blog = "properties/123456789"
site = "properties/987654321"
```

`[properties]` defines aliases usable anywhere a property is accepted: `ga report -P blog ...`.

### Property resolution chain

1. `-P/--property` global flag. Accepts `123456789`, `properties/123456789`, or a config alias.
2. `GA_PROPERTY` env var (same formats).
3. `default_property` in config.
4. If the credentials can see exactly one property (via account summaries), use it and print a one-line note to stderr: `Using properties/123456789 (only accessible property).`
5. Usage error (exit 2): `No property specified. Pass -P, set GA_PROPERTY, or set default_property in ~/.config/ga-cli/config.toml. Run "ga properties" to list available properties.`

Internal canonical form is always `properties/<id>`.

### `ga auth check`

Verifies the chain end to end. Output:

```json
{
  "ok": true,
  "credentials_source": "GA_CREDENTIALS",
  "credentials_path": "/Users/x/.config/ga-cli/sa.json",
  "principal": "ga-reader@my-proj.iam.gserviceaccount.com",
  "type": "service_account",
  "accessible_properties": 2,
  "default_property": "properties/123456789"
}
```

`--ping` additionally runs a 1-row report (`activeUsers`, `today`) against the resolved property and reports `"ping_ok": true` plus quota consumed. Failures exit with the mapped code (Section 6) so the skill can branch.

### `ga auth guide`

Prints numbered, copy-pasteable setup steps to stdout (this text is the command's data):

1. Create or pick a Google Cloud project.
2. Enable both APIs, with direct console URLs (`analyticsdata.googleapis.com`, `analyticsadmin.googleapis.com`).
3. Create a service account, download a JSON key.
4. In GA4 Admin > Property access management, add the SA email as Viewer.
5. Save the key to `~/.config/ga-cli/sa.json` and set `credentials` + `default_property` in config.
6. Verify: `ga auth check --ping`.

No browser automation, no gcloud invocation. Text only. OAuth interactive flow is a non-goal (ADC covers user-credential setups).

## 5. Output contract

### Modes

- Default: pretty JSON, 2-space indent, `ensure_ascii=False`, sorted keys off (insertion order is the documented order).
- `--compact`: single-line JSON.
- `--table`: rich table for humans. Table mode may truncate long cells; it carries no compatibility guarantee.
- `GA_AUTO_TABLE=1`: render tables when stdout is a TTY, JSON otherwise. Explicit flags override.
- `--table` and `--compact` together is a usage error (exit 2).
- JSON output never contains ANSI escapes. rich writes tables to stdout only in table mode; all rich styling elsewhere goes to stderr.

### Envelope policy

Same rule as goplaces, stated explicitly:

- Commands whose result can page or that carry report metadata return an object envelope with a named result key plus metadata siblings.
- Commands that return a complete result set return a bare JSON array (or a bare object for single-entity gets).

| Command | Shape |
|---|---|
| `report`, `realtime`, presets | envelope with `rows` |
| `accounts`, `properties list`, `streams`, `custom-dimensions`, `custom-metrics`, `key-events` | bare array (auto-paged internally to completion) |
| `properties get`, `auth check`, `compat`, `quota` | bare object |
| `meta` | object `{"dimensions": [...], "metrics": [...]}` |

`--results-only` (report/realtime/presets only): emit just the `rows` array, dropping the envelope. For scripting pipelines like `ga report ... --results-only | jq 'map(.sessions)'`.

### Report envelope

```json
{
  "property": "properties/123456789",
  "date_ranges": [
    {"name": "current", "start": "2026-06-12", "end": "2026-07-09"}
  ],
  "rows": [
    {"pagePath": "/blog/agentic-rag", "screenPageViews": 412, "activeUsers": 301}
  ],
  "row_count": 87,
  "returned": 20,
  "has_more": true
}
```

- `row_count` is the server-side total matching rows; `returned` is `len(rows)`; `has_more` is `offset + returned < row_count`.
- `totals` key present only with `--totals`. `quota` key present only with `--quota`.
- Empty result: `"rows": []`, `row_count: 0`, plus a stderr note in table mode only.

### Row flattening (core feature)

GA4 returns parallel arrays: `dimension_headers`/`metric_headers` define names, each row holds positional `dimension_values`/`metric_values` with string values. `flatten.py` converts each row to one flat object:

1. For each dimension i: `row[dim_headers[i].name] = normalize_dim(name, dimension_values[i].value)`.
2. For each metric j: `row[metric_headers[j].name] = coerce(metric_values[j].value, metric_headers[j].type_)`.

Metric coercion by declared `MetricType`:

| MetricType | Python type |
|---|---|
| TYPE_INTEGER | int |
| TYPE_FLOAT, TYPE_SECONDS, TYPE_MILLISECONDS, TYPE_CURRENCY, TYPE_FEET, TYPE_MILES, TYPE_METERS, TYPE_KILOMETERS | float |
| TYPE_STANDARD / unspecified | try int, then float, else keep string |

Unparseable or empty metric strings stay as-is (never crash on output).

Dimension normalization (`normalize_dim`), applied only to these date-like dimensions:

| Dimension | Wire | Emitted |
|---|---|---|
| `date`, `firstSessionDate` | `20260701` | `2026-07-01` |
| `dateHour` | `2026070114` | `2026-07-01T14` |
| `dateHourMinute` | `202607011432` | `2026-07-01T14:32` |
| `yearMonth` | `202607` | `2026-07` |
| `yearWeek` | `202628` | `2026-W28` |

All other dimensions pass through verbatim, including `(not set)` and `(other)`.

Multi-range reports: the API injects an implicit `dateRange` dimension; rename it to `date_range` in rows, valued with the range names (`current`, `previous`, or user-supplied names).

`--raw` (report/realtime only): skip flattening and emit the proto response converted losslessly via `MessageToDict`. Escape hatch for debugging; carries no shape guarantee.

### Lean field mapping for admin objects

Never emit full proto dumps. Hand-picked lean shapes, omitting empty fields:

```json
// accounts (bare array)
[{"account": "accounts/100", "display": "Sajal", "properties": [
    {"property": "properties/123456789", "display": "sajalsharma.com"}]}]

// properties list (bare array, flattened from account summaries)
[{"id": "123456789", "property": "properties/123456789",
  "display": "sajalsharma.com", "account": "accounts/100"}]

// properties get (bare object; from admin get_property)
{"id": "123456789", "property": "properties/123456789", "display": "sajalsharma.com",
 "time_zone": "Asia/Singapore", "currency": "USD", "industry": "TECHNOLOGY",
 "service_level": "GOOGLE_ANALYTICS_STANDARD", "created": "2023-04-02T09:11:00Z"}

// streams (bare array)
[{"id": "4567", "stream": "properties/123456789/dataStreams/4567", "type": "WEB_DATA_STREAM",
  "display": "Web", "uri": "https://sajalsharma.com", "measurement_id": "G-ABC123"}]

// key-events (bare array)
[{"id": "9876", "event_name": "sign_up", "counting_method": "ONCE_PER_EVENT", "custom": true}]

// custom-dimensions / custom-metrics (bare arrays)
[{"parameter": "author", "display": "Author", "scope": "EVENT"}]
```

## 6. Errors and exit codes

### Exit code taxonomy

| Code | Name | Meaning |
|---|---|---|
| 0 | ok | success (including empty results without `--fail-empty`) |
| 1 | error | unclassified runtime failure |
| 2 | usage | bad flags/args, DSL parse errors, invalid combinations, client-side validation |
| 3 | empty | zero rows and `--fail-empty` was set |
| 4 | auth | no credentials found, or credentials rejected (401/unauthenticated) |
| 5 | not_found | property or resource does not exist (404) |
| 6 | permission | credentials valid but lack access (403 non-quota) |
| 7 | quota | rate limited or property token quota exhausted (429, 403 quota reasons) |
| 8 | retryable | 5xx, network timeout, connection failure |

Documented in README and `references/commands.md`; agents branch on codes, not stderr text.

### Exception mapping (`errors.py`)

One decorator/wrapper around every command body maps exceptions to exits:

| Exception | Exit |
|---|---|
| `click.UsageError`, DSL/date/order parse errors, validation | 2 |
| `google.auth.exceptions.DefaultCredentialsError` | 4 |
| `google.api_core.exceptions.Unauthenticated` | 4 |
| `google.api_core.exceptions.PermissionDenied` | 6 |
| `google.api_core.exceptions.NotFound` | 5 |
| `google.api_core.exceptions.ResourceExhausted`, `TooManyRequests` | 7 |
| `google.api_core.exceptions.InvalidArgument` | 2 |
| `DeadlineExceeded`, `ServiceUnavailable`, `InternalServerError`, `Aborted`, `retry.RetryError`, `ConnectionError` | 8 |
| anything else | 1 |

### Error message style

Text on stderr, one short problem statement, then the remediation command. Never a stack trace (except with `--debug`, which re-raises). Errors are not JSON; the machine contract is the exit code.

Required remediation texts:

- Exit 4 (no creds): `No Google credentials found. Run "ga auth guide" for setup steps.`
- Exit 6 on a property call: `Access denied to properties/123456789. Grant Viewer access to <principal> in GA4 Admin > Property access management, or check the property ID with "ga properties".`
- Exit 2 from InvalidArgument mentioning a field name: append `Hint: run "ga meta --search <field>" to find valid metric and dimension names.` (surface Google's own message verbatim first; it names the bad field).
- Exit 7: append `Check remaining tokens with "ga quota".`

### stdout/stderr discipline

stdout carries exactly one JSON document (or one table) per invocation, or nothing on error. Everything else is stderr. This is a hard rule enforced by tests.

## 7. Global flags

Registered on the root group, available to every subcommand (mirroring ynab-cli's pattern of stashing in `ctx.obj`):

| Flag | Env | Default | Purpose |
|---|---|---|---|
| `-P, --property TEXT` | `GA_PROPERTY` | config / auto | Property ID, resource name, or config alias |
| `--credentials PATH` | `GA_CREDENTIALS` | chain (Section 4) | Service account JSON path |
| `--config PATH` | `GA_CONFIG` | `~/.config/ga-cli/config.toml` | Config file |
| `--table` | `GA_AUTO_TABLE` (TTY-conditional) | off | Human table output |
| `--compact` | | off | Single-line JSON |
| `--timeout FLOAT` | | 30.0 | Per-request timeout seconds |
| `--debug` | | off | Re-raise exceptions with traceback (stderr) |
| `--version` | | | Print version, exit 0 |

No short flags other than `-P` (and per-command `-m/-d/-r/-f/-o` listed below). `--flag value` and `--flag=value` both work (Click default).

## 8. Command reference

Command style: noun or noun-verb, flat where possible. Primary input positional only where unambiguous (`properties get <id>`). All examples show JSON-default output.

### 8.1 `ga accounts`

List account summaries (the discovery primitive). No flags beyond globals. Auto-pages `list_account_summaries` to completion. Bare array output (shape in Section 5).

### 8.2 `ga properties [list]` / `ga properties get [PROPERTY]`

- `list` (default subcommand): flattened property list from account summaries. Bare array.
- `get`: detail via admin `get_property`. `PROPERTY` positional optional; falls back to the resolution chain. Bare object.

Implementation note: admin `list_properties` requires a `parent:accounts/N` filter; derive listing from `list_account_summaries` instead, one call for everything.

### 8.3 Admin listers: `ga streams`, `ga custom-dimensions`, `ga custom-metrics`, `ga key-events`

All: property from the chain, auto-paged, bare-array lean output (shapes in Section 5). Admin methods: `list_data_streams`, `list_custom_dimensions`, `list_custom_metrics`, `list_key_events`.

### 8.4 `ga meta`

Field discovery so agents never guess API names. Data API `get_metadata(name=f"{property}/metadata")`, which includes property-specific custom fields.

| Flag | Default | Purpose |
|---|---|---|
| `--search TEXT` | | Case-insensitive substring match on api name, ui name, and description |
| `--type [dimensions\|metrics\|all]` | all | Restrict kind |
| `--custom` | off | Only custom (property-defined) fields |
| `--full` | off | Include full descriptions (token-heavy; default output is name, display, category only) |

```bash
ga meta --search engagement --type metrics
```

```json
{
  "metrics": [
    {"name": "engagementRate", "display": "Engagement rate", "category": "Session"},
    {"name": "userEngagementDuration", "display": "User engagement", "category": "Session"}
  ],
  "dimensions": []
}
```

With `--full`, each entry adds `"description"` and (metrics) `"type"` and `"expression"`. Custom fields carry `"custom": true`.

### 8.5 `ga compat --metrics CSV --dims CSV`

Data API `check_compatibility`. Validates a combination before spending report tokens.

```json
{"compatible": false,
 "incompatible_metrics": [{"name": "purchaserRate", "reason": "INCOMPATIBLE"}],
 "incompatible_dimensions": []}
```

`compatible` is true iff both lists are empty. Exit 0 either way (incompatibility is data, not an error).

### 8.6 `ga report` (the core primitive)

Data API `run_report`.

| Flag | Default | Notes |
|---|---|---|
| `-m, --metrics CSV` | required | 1-10 metrics (API max 10) |
| `-d, --dims CSV` | none | 0-9 dimensions (API max 9) |
| `-r, --range SPEC` | `28d` | Repeatable, max 4. Grammar in Section 9 |
| `--compare [prev\|yoy]` | | Adds a computed second range; usage error with multiple `-r` |
| `-f, --filter EXPR` | | Repeatable, AND semantics. Grammar in Section 10 |
| `--filter-any EXPR` | | Repeatable, forms one OR group ANDed with `-f` filters |
| `--filter-json JSON\|@FILE` | | Raw FilterExpression escape hatch; usage error if combined with `-f`/`--filter-any`. Applied as dimension filter unless wrapped `{"metric": {...}}` / `{"dimension": {...}}` |
| `--case-sensitive` | off | String filters match case-sensitively |
| `-o, --order SPEC` | first metric desc | Repeatable. Grammar in Section 11. `-o none` disables |
| `--limit INT` | 20 | 1-250000 (API max per request) |
| `--offset INT` | 0 | |
| `--all` | off | Auto-page until all rows fetched. Loop-guarded: hard stop + stderr warning at 250k accumulated rows |
| `--totals` | off | Request TOTAL aggregation; adds `totals` object to envelope |
| `--quota` | off | Request property quota; adds `quota` object to envelope |
| `--fail-empty` | off | Exit 3 when zero rows |
| `--results-only` | off | Emit bare rows array |
| `--raw` | off | Lossless proto dump, no flattening |

Examples:

```bash
# Daily trend, last 28 days
ga report -m activeUsers,sessions -d date -o date

# Top blog posts this month
ga report -m screenPageViews -d pagePath -f 'pagePath=^/blog' -r mtd --limit 10

# Sessions by channel, this 28 days vs previous 28
ga report -m sessions -d sessionDefaultChannelGroup --compare prev

# Everything, piped
ga report -m eventCount -d eventName --all --results-only | jq 'map(.eventName)'
```

Validation before any network call: metric/dim counts within API limits, limit/offset ranges, range count <= 4, compare/range exclusivity, filter and order fields must appear in the request or be valid API names (fields referenced in `-f`/`-o` that are not in `-m`/`-d` are allowed by the API for filters but not for ordering; enforce: order fields must be in the request, filter fields may be any name and are classified metric-vs-dimension by membership in `-m`).

`--totals` output shape: `"totals": {"sessions": 4102, "activeUsers": 2988}` (flattened like a row, dimensions omitted).

`--quota` output shape (from `PropertyQuota`, omitting the server-error counters):

```json
"quota": {
  "tokens_per_day": {"consumed": 14, "remaining": 199986},
  "tokens_per_hour": {"consumed": 14, "remaining": 39986},
  "concurrent_requests": {"consumed": 0, "remaining": 10}
}
```

### 8.7 `ga realtime`

Data API `run_realtime_report`. Last-30-minutes activity.

| Flag | Default | Notes |
|---|---|---|
| `-m, --metrics CSV` | `activeUsers` | |
| `-d, --dims CSV` | none | Realtime supports a restricted dimension set |
| `--minutes INT` | 30 | 1-30; maps to one minute range `{start_minutes_ago: N-1, end_minutes_ago: 0}` |
| `--limit INT` | 20 | |
| `--fail-empty`, `--results-only`, `--raw` | | as in report |

Envelope: like report but `"minutes": 30` replaces `date_ranges`. No filters in v1 (realtime filter support: deferred).

### 8.8 Presets: `ga pages`, `ga sources`, `ga events`, `ga trend`

Sugar over `report` for the four most common questions. Each accepts `-r/--range`, `--limit` (default 10), `-f/--filter`, `--compare`, `--fail-empty`, `--results-only`, and nothing else. Help text shows the equivalent `ga report` invocation.

| Preset | Dimensions | Metrics | Order |
|---|---|---|---|
| `pages` | `pagePath` | `screenPageViews,activeUsers` | `-screenPageViews` |
| `sources` | `sessionDefaultChannelGroup` | `sessions,activeUsers` | `-sessions` |
| `events` | `eventName` | `eventCount,activeUsers` | `-eventCount` |
| `trend` | `date` | `activeUsers,sessions,screenPageViews` | `date` (asc) |

### 8.9 `ga quota`

Runs a minimal report (`-m activeUsers -r today --limit 1 --quota`) and emits only the quota object (bare object). Cheap way for agents to check budget. Exit 7 if already exhausted.

### 8.10 `ga auth check` / `ga auth guide`

Specified in Section 4.

### 8.11 `ga skill install` / `ga skill show` / `ga skill path`

The skill ships inside the package (`ga_cli/_skill/` package data), so every install channel (PyPI, brew, source) can deploy it without cloning the repo.

- `install`: copy the bundled skill to `~/.claude/skills/ga-cli/`. `--project` targets `./.claude/skills/ga-cli/` instead. `--force` overwrites an existing copy; without it, an existing install is compared and the command reports `{"ok": true, "status": "up-to-date"}` or asks for `--force` (exit 2) when contents differ.
- `show`: print the bundled SKILL.md to stdout.
- `path`: print the absolute path of the bundled skill directory (for manual copying or symlinking).

Output of `install` (JSON, like everything else):

```json
{"ok": true, "installed": "/Users/x/.claude/skills/ga-cli", "files": 2, "version": "1.0.0"}
```

The skill's frontmatter carries no version; the CLI version at install time is echoed so drift is diagnosable. Reinstall after upgrading the CLI: `ga skill install --force`.

### Deferred commands (v2 sketches, do not build in v1)

- `ga pivot` (run_pivot_report), `ga batch` (batch_run_reports with `@file` of report specs)
- `ga funnel` (v1alpha AlphaAnalyticsDataClient)
- `ga audience-export create|status|query`
- `ga search-console ...` (different API family; likely separate tool)

## 9. Date range grammar (`dates.py`)

`--range SPEC` where `SPEC := [name=]RANGE`:

| RANGE | Meaning |
|---|---|
| `today`, `yesterday` | single day |
| `Nd` | last N days ending today: `start = today-(N-1)`, e.g. `7d`, `28d`, `90d` |
| `wtd`, `mtd`, `qtd`, `ytd` | week (Mon start) / month / quarter / year to date, ending today |
| `YYYY-MM-DD` | single day |
| `YYYY-MM-DD:YYYY-MM-DD` | explicit inclusive range |
| `START:END` GA-native tokens | passthrough, e.g. `28daysAgo:yesterday` |
| bare GA token, e.g. `7daysAgo` | start = token, end = `today` (gog parity) |

- Default range name: first range `current`, second `previous`, then `range_2`, `range_3`. `name=` overrides: `-r 'launch=2026-06-01:2026-06-15'`.
- `--compare prev`: second range = same length immediately preceding the first (for `28d`: `55daysAgo:28daysAgo` computed as concrete dates client-side).
- `--compare yoy`: same calendar dates one year earlier.
- Resolution to concrete `YYYY-MM-DD` happens client-side in the machine's local timezone; concrete dates are echoed in the envelope's `date_ranges` so output is self-describing. GA-native passthrough tokens are sent verbatim and echoed verbatim.
- Invalid spec: exit 2 with the accepted forms listed in the message (teach-in-error, gog style).

## 10. Filter DSL (`filters.py`)

`EXPR := FIELD OP VALUE`, compiled to a `FilterExpression`.

| OP | Meaning | Maps to |
|---|---|---|
| `==` | equals | stringFilter EXACT; inListFilter when VALUE contains `\|`; numericFilter EQUAL on metric fields |
| `!=` | not equals | notExpression(EXACT / inList) |
| `=@` / `!@` | contains / not contains | stringFilter CONTAINS |
| `=^` | begins with | stringFilter BEGINS_WITH |
| `=$` | ends with | stringFilter ENDS_WITH |
| `=~` / `!~` | regex / not regex | stringFilter FULL_REGEXP |
| `>` `>=` `<` `<=` | numeric compare | numericFilter GREATER_THAN etc. |

Rules:

- Field classification: FIELD is a metric iff it appears in the request's `-m` list; otherwise dimension. Metric filters and dimension filters compile to the request's `metric_filter` and `dimension_filter` respectively (each an andGroup).
- Multiple `-f` combine as AND. All `--filter-any` expressions form one orGroup, ANDed with the rest. Mixed metric/dimension expressions inside `--filter-any` are a usage error (API cannot OR across the two).
- In-list: `country==United States|Canada|Singapore`. Literal pipe in a value: `\|`.
- String matching is case-insensitive by default (`case_sensitive=False`); `--case-sensitive` flips every string filter in the invocation.
- Numeric VALUE parsed as int else float; numeric op with non-numeric value is exit 2.
- Anything the DSL cannot express (nested groups, between, empty-value filters): `--filter-json`, raw FilterExpression JSON, inline or `@file`.

Examples:

```bash
-f 'pagePath=^/blog'                       # prefix
-f 'country==United States|Canada'         # in-list
-f 'sessions>100' -m sessions,activeUsers  # metric filter
--filter-any 'source=@github' --filter-any 'source=@linkedin'
```

## 11. Order grammar (`orders.py`)

`-o SPEC`, repeatable, order preserved:

- `field` ascending, `-field` descending: `-o -sessions -o pagePath`.
- Metric vs dimension resolved by membership in `-m` (metrics) else `-d` (dimensions); a field in neither is exit 2.
- Default when `-o` absent: first metric descending (deterministic default for "top N" ergonomics). `-o none` sends no ordering (API natural order).
- Deferred: dimension order types (alphanumeric vs numeric variants).

## 12. Network behavior

- Timeout: `--timeout` (default 30s) passed as per-call `timeout=` to every client method.
- Retries: rely on google-api-core's built-in default retry for transient errors; do not hand-roll. After exhaustion, the mapped exit code applies (8 for transport, 7 for quota).
- Pagination (`--all`): follow `offset += limit` until `offset >= row_count`, cap accumulated rows at 250000 with a stderr warning, guard against non-advancing offsets.
- One API call per invocation in the common path. Presets are one call. `auth check --ping` and `quota` are one metadata/report call each.

## 13. Skill (`skills/ga-cli/`)

Layout mirrors hevy-cli: `skills/ga-cli/SKILL.md` + `skills/ga-cli/references/commands.md`. The directory is named `skills/` (plural) at the repo root so ecosystem installers that scan for SKILL.md files discover it.

### Installing the skill (document all of these in README)

| Method | Command | Notes |
|---|---|---|
| Bundled installer (recommended) | `ga skill install` | Works from any CLI install channel, including brew. `--project` for a project-local install. See Section 8.11 |
| Homebrew | `brew install sajal2692/tap/ga-cli` then `ga skill install` | The formula caveat prints this exact follow-up |
| skills CLI | `npx skills add sajal2692/ga-cli` | Discovers `skills/ga-cli/SKILL.md` from the public repo |
| Manual | `cp -r skills/ga-cli ~/.claude/skills/` | From a checkout |

Default target is global (`~/.claude/skills/`) since analytics questions are not project-scoped; agents and users can still invoke it explicitly with `/ga-cli` once installed.

SKILL.md frontmatter and required content:

```markdown
---
name: ga-cli
description: Query Google Analytics 4 via the ga CLI. Use when the user asks about website traffic, visitors, page views, sessions, top pages, traffic sources, referrers, realtime activity, events, engagement, or any GA4 metrics for their site. Triggers on analytics, GA4, Google Analytics, site traffic, or visitor questions.
---
```

Body sections (keep the whole file under ~120 lines; depth lives in references/commands.md):

1. One-line setup note: requires configured credentials; verify with `ga auth check`; run `ga auth guide` if not set up.
2. Quick start: `ga auth check`, `ga properties`, `ga trend -r 7d`.
3. Common tasks, NL question to command mapping:
   - traffic overview: `ga trend -r 28d`
   - top pages: `ga pages -r 7d --limit 10`
   - traffic sources: `ga sources -r 28d`
   - who is on now: `ga realtime -d unifiedScreenName`
   - period comparison: `ga report -m sessions -d date --compare prev`
   - filtered section traffic: `ga pages -f 'pagePath=^/blog'`
   - unknown field name: `ga meta --search <term>` first, then report
4. Key patterns:
   - Output is JSON by default; parse it directly, no flags needed.
   - Exit codes: 3 = empty (only with --fail-empty), 4 = run auth guide, 6 = access grant missing, 7 = quota; branch, do not parse stderr.
   - Never guess metric/dimension names; `ga meta --search` is one cheap call.
   - Use `--compare prev` instead of two invocations.
   - Property defaults from config; pass `-P <alias>` only for non-default properties.
5. Pointer to `references/commands.md` for the full flag reference (generated content mirroring Section 8 tables, kept in sync manually at release).

## 14. Testing

- Framework: pytest + Click's `CliRunner`. Lint/type: ruff + mypy (strict on `src/`).
- Unit tests monkeypatch `ga_cli.clients.get_data_client` / `get_admin_client` with fakes returning proto messages built from the real `data_types` / `admin_v1beta` types constructed in fixtures (no network, no recorded HTTP).
- Golden tests: fixture proto response -> expected stdout JSON in `tests/golden/*.json`; assert byte-equal output. Cover: flattening (all metric types, date normalization, multi-range), envelope fields, results-only, compact, empty results.
- Contract tests: stdout purity (nothing but the JSON document on stdout), exit codes for each mapped exception (raise from fake client), usage errors for every documented invalid combination, filter/date/order parsers (table-driven).
- E2E (opt-in): `pytest -m e2e`, skipped unless `GA_E2E=1` and credentials + `GA_PROPERTY` resolve; runs `auth check --ping`, `meta --search sessions`, `trend -r 7d` against the real property.
- Coverage target: 85% on `src/ga_cli`, enforced in CI (`ci.yml`, Section 3).

## 15. Milestones (build order)

- M0 scaffold: pyproject, src layout, root group + global flags, config.py, clients.py, errors.py with exit map, output.py. `ga version`, `ga auth check`, `ga auth guide`, `ga accounts`, `ga properties list|get`. Installable via `uv tool install`, tests green.
- M1 reporting core: dates.py, flatten.py, orders.py, `ga report` (ranges, order, limit/offset/all, totals, quota, fail-empty, results-only, raw), `ga realtime`. gog analytics parity reached (Appendix A).
- M2 query power: filters.py DSL + `--filter-json`, `--compare`, `ga meta`, `ga compat`.
- M3 breadth: admin listers (`streams`, `custom-dimensions`, `custom-metrics`, `key-events`), presets, `ga quota`.
- M4 agent surface: skill + references/commands.md, `ga skill install|show|path`, README (install channels, auth setup, exit code table), `--table` polish, CHANGELOG.
- M5 release v1.0.0: public GitHub repo (`sajal2692/ga-cli`), CI green, PyPI trusted publishing wired, tag `v1.0.0`, publish, brew tap formula in `sajal2692/homebrew-tap`, smoke-test all four install channels plus `ga skill install`, `npx skills add sajal2692/ga-cli` verified.
- Deferred (v2+): pivot/batch, funnels (v1alpha), audience exports, realtime filters, `--select` projection, brew formula auto-bump, MCP wrapper if ever needed.

## 16. Non-goals

- Any write/mutation operation against GA (admin mutations are never bound).
- OAuth interactive browser flow (ADC covers user credentials).
- Universal Analytics (GA3), BigQuery export management, Search Console (separate API; separate tool if wanted).
- Multi-profile keyring storage; interactive prompts; shell completion (Click ships basic completion for free, do not invest beyond that).
- Windows support guarantees (should work, untested).

## Appendix A: gog analytics parity checklist

| gog | ga-cli equivalent |
|---|---|
| `gog analytics accounts` | `ga accounts` |
| `gog analytics report <property>` | `ga report -P <property>` (or config default) |
| `--from 7daysAgo --to today` | `-r 7daysAgo:today` or `-r 7d`; bare `-r 7daysAgo` also accepted |
| `--dimensions date` (default date) | `-d date` (no implicit default dims; presets cover the common cases) |
| `--metrics activeUsers` (default) | `-m activeUsers` (explicit, required on `report`; `ga trend` covers the no-thought case) |
| `--max 100` / `--offset` | `--limit` / `--offset` (default 20, deliberate) |
| `--fail-empty` (exit 3) | `--fail-empty` (exit 3, same semantics) |
| `--json` envelope with raw rows | JSON default with flattened rows; `--raw` for wire shape |
| exit codes 0/2/3/4/5/6/7/8 | same taxonomy (Section 6) |

Deliberate differences: property comes from config/env/flag instead of a required positional; metrics are explicit rather than defaulted; rows are flattened objects.

## Appendix B: API surface used

Data API (`google.analytics.data_v1beta`, `BetaAnalyticsDataClient`):
- `run_report(RunReportRequest)` with: `property`, `date_ranges`, `dimensions`, `metrics`, `dimension_filter`, `metric_filter`, `order_bys`, `limit`, `offset`, `metric_aggregations`, `return_property_quota`
- `run_realtime_report(RunRealtimeReportRequest)` with `minute_ranges`
- `get_metadata(name="properties/N/metadata")`
- `check_compatibility(CheckCompatibilityRequest)`

Admin API (`google.analytics.admin_v1beta`, `AnalyticsAdminServiceClient`):
- `list_account_summaries()` (paged)
- `get_property(name="properties/N")`
- `list_data_streams(parent)`, `list_custom_dimensions(parent)`, `list_custom_metrics(parent)`, `list_key_events(parent)`

Quotas (standard properties, for README): ~200k core tokens/day, ~40k/hour, 10 concurrent requests; check live state with `ga quota`. Report token cost scales with rows, date range, and cardinality.

## Appendix C: references

- gogcli: https://github.com/steipete/gogcli (automation contract, exit codes, skills generation)
- goplaces: https://github.com/steipete/goplaces (lean output mapping, envelope policy, defaults)
- Data API: https://developers.google.com/analytics/devguides/reporting/data/v1
- Admin API: https://developers.google.com/analytics/devguides/config/admin/v1
- Python clients: `google-analytics-data` (>=0.23), `google-analytics-admin` (>=0.30)
