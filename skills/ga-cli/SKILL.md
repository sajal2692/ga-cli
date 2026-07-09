---
name: ga-cli
description: Query Google Analytics 4 via the ga4 CLI. Use when the user asks about website traffic, visitors, page views, sessions, top pages, traffic sources, referrers, realtime activity, events, engagement, or any GA4 metrics for their site. Triggers on analytics, GA4, Google Analytics, site traffic, or visitor questions.
---

# ga-cli

Query Google Analytics 4 from the terminal with the `ga4` binary. Requires configured
credentials: verify with `ga4 auth check`; if it fails, run `ga4 auth guide` and walk the
user through the printed steps.

## Quick start

```bash
ga4 auth check          # credentials and property access
ga4 properties          # list accessible properties
ga4 trend -r 7d         # daily users/sessions/views, last 7 days
```

## Common tasks

| Question | Command |
|---|---|
| Traffic overview | `ga4 trend -r 28d` |
| Top pages | `ga4 pages -r 7d --limit 10` |
| Traffic sources | `ga4 sources -r 28d` |
| Who is on the site now | `ga4 realtime -d unifiedScreenName` |
| Period comparison | `ga4 report -m sessions -d date --compare prev` |
| Blog/section traffic | `ga4 pages -f 'pagePath=^/blog'` |
| Unknown field name | `ga4 meta --search <term>` first, then report |
| Custom report | `ga4 report -m <metrics> -d <dims> -r <range> -f <filter> -o <order>` |

## Key patterns

- Output is JSON on stdout by default; parse it directly, no flags needed.
- Exit codes, branch on these instead of parsing stderr:
  - 0 ok (empty results still exit 0 unless `--fail-empty`)
  - 2 usage error, 3 empty with `--fail-empty`
  - 4 no/bad credentials: run `ga4 auth guide`
  - 5 not found, 6 access grant missing on the property
  - 7 quota exhausted: check `ga4 quota`, 8 transient, retry
- Never guess metric or dimension names; `ga4 meta --search <term>` is one cheap call.
  Check combinations with `ga4 compat -m <metrics> -d <dims>` before large reports.
- Use `--compare prev` (or `yoy`) instead of running two reports.
- The property comes from config; pass `-P <alias-or-id>` only for non-default properties.
- Filters: `-f 'pagePath=^/blog'` (prefix), `-f 'country==United States|Canada'`
  (in-list), `-f 'sessions>100'` (metric). Repeat `-f` for AND, `--filter-any` for OR.
- Ranges: `7d`, `28d`, `mtd`, `ytd`, `2026-06-01:2026-06-15`, `--compare prev|yoy`.
- `--results-only` emits the bare rows array for piping to jq.

## Full reference

See [references/commands.md](references/commands.md) for every command, flag,
the filter DSL, the date range grammar, and output shapes.
