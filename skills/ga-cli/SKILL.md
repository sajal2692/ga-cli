---
name: ga-cli
description: Query Google Analytics 4 via the ga CLI. Use when the user asks about website traffic, visitors, page views, sessions, top pages, traffic sources, referrers, realtime activity, events, engagement, or any GA4 metrics for their site. Triggers on analytics, GA4, Google Analytics, site traffic, or visitor questions.
---

# ga-cli

Query Google Analytics 4 from the terminal with the `ga` binary. Requires configured
credentials: verify with `ga auth check`; if it fails, run `ga auth guide` and walk the
user through the printed steps.

## Quick start

```bash
ga auth check          # credentials and property access
ga properties          # list accessible properties
ga trend -r 7d         # daily users/sessions/views, last 7 days
```

## Common tasks

| Question | Command |
|---|---|
| Traffic overview | `ga trend -r 28d` |
| Top pages | `ga pages -r 7d --limit 10` |
| Traffic sources | `ga sources -r 28d` |
| Who is on the site now | `ga realtime -d unifiedScreenName` |
| Period comparison | `ga report -m sessions -d date --compare prev` |
| Blog/section traffic | `ga pages -f 'pagePath=^/blog'` |
| Unknown field name | `ga meta --search <term>` first, then report |
| Custom report | `ga report -m <metrics> -d <dims> -r <range> -f <filter> -o <order>` |

## Key patterns

- Output is JSON on stdout by default; parse it directly, no flags needed.
- Exit codes, branch on these instead of parsing stderr:
  - 0 ok (empty results still exit 0 unless `--fail-empty`)
  - 2 usage error, 3 empty with `--fail-empty`
  - 4 no/bad credentials: run `ga auth guide`
  - 5 not found, 6 access grant missing on the property
  - 7 quota exhausted: check `ga quota`, 8 transient, retry
- Never guess metric or dimension names; `ga meta --search <term>` is one cheap call.
  Check combinations with `ga compat -m <metrics> -d <dims>` before large reports.
- Use `--compare prev` (or `yoy`) instead of running two reports.
- The property comes from config; pass `-P <alias-or-id>` only for non-default properties.
- Filters: `-f 'pagePath=^/blog'` (prefix), `-f 'country==United States|Canada'`
  (in-list), `-f 'sessions>100'` (metric). Repeat `-f` for AND, `--filter-any` for OR.
- Ranges: `7d`, `28d`, `mtd`, `ytd`, `2026-06-01:2026-06-15`, `--compare prev|yoy`.
- `--results-only` emits the bare rows array for piping to jq.

## Full reference

See [references/commands.md](references/commands.md) for every command, flag,
the filter DSL, the date range grammar, and output shapes.
