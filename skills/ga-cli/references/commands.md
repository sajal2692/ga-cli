# ga-cli command reference

All commands emit JSON on stdout by default. Data goes to stdout; progress, warnings,
and errors go to stderr. Errors are plain text plus an exit code; branch on the code.

## Global flags (every command)

| Flag | Env | Default | Purpose |
|---|---|---|---|
| `-P, --property` | `GA_PROPERTY` | config / auto | Property ID, `properties/<id>`, or config alias |
| `--credentials` | `GA_CREDENTIALS` | chain | Service account JSON path |
| `--config` | `GA_CONFIG` | `~/.config/ga-cli/config.toml` | Config file |
| `--table` | `GA_AUTO_TABLE=1` (TTY) | off | Human table output |
| `--compact` | | off | Single-line JSON |
| `--timeout` | | 30.0 | Per-request timeout seconds |
| `--debug` | | off | Re-raise exceptions with traceback |
| `--version` | | | Print version, exit 0 |

Credential resolution: `--credentials` > `GA_CREDENTIALS` > config `credentials` >
`GOOGLE_APPLICATION_CREDENTIALS` > application default credentials.

Property resolution: `-P` > `GA_PROPERTY` > config `default_property` > sole accessible
property. Aliases come from the config `[properties]` table.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success (including empty results without `--fail-empty`) |
| 1 | unclassified runtime failure |
| 2 | usage: bad flags, DSL parse errors, invalid combinations |
| 3 | zero rows and `--fail-empty` was set |
| 4 | no credentials found, or credentials rejected |
| 5 | property or resource does not exist |
| 6 | credentials valid but lack access |
| 7 | rate limited or quota exhausted |
| 8 | transient failure (5xx, timeout, network); retry |

## Commands

### Discovery

- `ga4 accounts` - account summaries with nested properties. Bare array.
- `ga4 properties [list]` - flattened property list. Bare array.
- `ga4 properties get [PROPERTY]` - property detail (time zone, currency, service level).
- `ga4 streams` - data streams (measurement IDs). Bare array.
- `ga4 custom-dimensions` / `ga4 custom-metrics` - property-defined fields. Bare arrays.
- `ga4 key-events` - key events with counting method. Bare array.
- `ga4 meta [--search TEXT] [--type dimensions|metrics|all] [--custom] [--full]` -
  valid field names. Returns `{"dimensions": [...], "metrics": [...]}`.
- `ga4 compat -m CSV -d CSV` - checks a combination before spending tokens. Returns
  `{"compatible": bool, "incompatible_metrics": [...], "incompatible_dimensions": [...]}`.
- `ga4 quota` - remaining report tokens. Bare object.

### Auth

- `ga4 auth check [--ping]` - verifies the credential chain; `--ping` runs a 1-row report
  and reports quota. Failures exit with the mapped code.
- `ga4 auth guide` - copy-pasteable setup steps (service account, API enablement, grant).

### Reporting

`ga4 report` flags:

| Flag | Default | Notes |
|---|---|---|
| `-m, --metrics CSV` | required | 1-10 metrics |
| `-d, --dims CSV` | none | 0-9 dimensions |
| `-r, --range SPEC` | `28d` | Repeatable, max 4 |
| `--compare prev\|yoy` | | Computed second range; not with multiple `-r` |
| `-f, --filter EXPR` | | Repeatable, AND semantics |
| `--filter-any EXPR` | | Repeatable, one OR group ANDed with `-f` |
| `--filter-json JSON\|@FILE` | | Raw FilterExpression escape hatch |
| `--case-sensitive` | off | String filters match case-sensitively |
| `-o, --order SPEC` | first metric desc | `field` asc, `-field` desc, `none` disables |
| `--limit` | 20 | 1-250000 |
| `--offset` | 0 | |
| `--all` | off | Auto-page all rows (hard cap 250000). With an explicit `--limit`, pages in steps of that size |
| `--totals` | off | Adds `totals` object |
| `--quota` | off | Adds `quota` object |
| `--fail-empty` | off | Exit 3 on zero rows |
| `--results-only` | off | Bare rows array |
| `--raw` | off | Lossless API response, no flattening (debug only) |

Envelope shape:

```json
{
  "property": "properties/123456789",
  "date_ranges": [{"name": "current", "start": "2026-06-12", "end": "2026-07-09"}],
  "rows": [{"pagePath": "/blog/post", "screenPageViews": 412}],
  "row_count": 87,
  "returned": 20,
  "has_more": true
}
```

Rows are flat objects: dimensions as strings (dates normalized to ISO), metrics as
numbers. Multi-range reports add a `date_range` key valued with the range name.

Multi-range unit note: with N date ranges the API counts `row_count`, `--limit`, and
`--offset` in base rows (unique dimension combinations), while `rows`/`returned`
contain one row per range (N per base row, zero-filled). `has_more` and `--all`
account for this.

`ga4 realtime [-m CSV] [-d CSV] [--minutes 1-30] [--limit N]` - last-30-minutes
activity. Envelope has `minutes` instead of `date_ranges`.

### Presets

Sugar over `ga4 report`; accept `-r`, `--limit` (default 10), `-f`, `--compare`,
`--fail-empty`, `--results-only`.

| Preset | Dimensions | Metrics | Order |
|---|---|---|---|
| `ga4 pages` | pagePath | screenPageViews, activeUsers | -screenPageViews |
| `ga4 sources` | sessionDefaultChannelGroup | sessions, activeUsers | -sessions |
| `ga4 events` | eventName | eventCount, activeUsers | -eventCount |
| `ga4 trend` | date | activeUsers, sessions, screenPageViews | date |

### Skill

- `ga4 skill install [--project] [--force]` - copy the bundled skill to
  `~/.claude/skills/ga-cli/` (or `./.claude/skills/` with `--project`).
- `ga4 skill show` - print the bundled SKILL.md.
- `ga4 skill path` - print the bundled skill directory.

## Date range grammar

| Spec | Meaning |
|---|---|
| `today`, `yesterday` | single day |
| `Nd` | last N days ending today (`7d`, `28d`, `90d`) |
| `wtd`, `mtd`, `qtd`, `ytd` | week (Mon) / month / quarter / year to date |
| `YYYY-MM-DD` | single day |
| `YYYY-MM-DD:YYYY-MM-DD` | explicit inclusive range |
| `28daysAgo:yesterday` | GA-native tokens, passed through verbatim |
| `7daysAgo` | start token, end today |
| `name=RANGE` | named range (`launch=2026-06-01:2026-06-15`) |

`--compare prev` adds the same-length period immediately before the first range;
`--compare yoy` the same calendar dates one year earlier.

## Filter DSL

`FIELD OP VALUE`; a field is a metric iff it appears in `-m`, otherwise a dimension.

| OP | Meaning |
|---|---|
| `==` | equals (in-list when VALUE contains `\|`; numeric on metrics) |
| `!=` | not equals |
| `=@` / `!@` | contains / not contains |
| `=^` | begins with |
| `=$` | ends with |
| `=~` / `!~` | regex / not regex (full match) |
| `>` `>=` `<` `<=` | numeric compare |

- Repeat `-f` for AND. All `--filter-any` values form one OR group ANDed with the rest.
- In-list: `country==United States|Canada`. Literal pipe: `\|`.
- String matching is case-insensitive unless `--case-sensitive`.
- Anything else (nested groups, between, empty values): `--filter-json '<json>'` or
  `--filter-json @file.json` with a raw FilterExpression, optionally wrapped as
  `{"metric": {...}}` or `{"dimension": {...}}`.

## Examples

```bash
ga4 report -m activeUsers,sessions -d date -o date                  # daily trend
ga4 report -m screenPageViews -d pagePath -f 'pagePath=^/blog' -r mtd --limit 10
ga4 report -m sessions -d sessionDefaultChannelGroup --compare prev
ga4 report -m eventCount -d eventName --all --results-only | jq 'map(.eventName)'
ga4 realtime -d unifiedScreenName
ga4 meta --search engagement --type metrics
```
