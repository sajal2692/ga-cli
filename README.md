# ga-cli

Agent-native command-line interface for Google Analytics 4. One binary (`ga`),
task-first commands, flattened JSON that agents and scripts can consume directly,
stable exit codes for branching, and zero interactive prompts. Read-only by
construction: only read methods of the GA4 Data and Admin APIs are ever bound.

```bash
ga trend -r 7d                                  # daily users/sessions/views
ga pages -f 'pagePath=^/blog' --limit 10        # top blog posts
ga report -m sessions -d sessionDefaultChannelGroup --compare prev
ga realtime -d unifiedScreenName                # who is on the site now
```

## Install

| Channel | Command |
|---|---|
| PyPI (primary) | `uv tool install ga-cli` (or `pipx install ga-cli`, `pip install ga-cli`) |
| Homebrew | `brew install sajal2692/tap/ga-cli` |
| From source | `uv tool install git+https://github.com/sajal2692/ga-cli` |
| Local dev | `uv tool install --editable ~/code/active/tools/ga-cli` |

Verify with `ga --version`.

## Auth setup

`ga auth guide` prints the full copy-pasteable steps. Summary:

1. Create a Google Cloud project and enable `analyticsdata.googleapis.com` and
   `analyticsadmin.googleapis.com`.
2. Create a service account and download a JSON key.
3. In GA4 Admin > Property access management, add the service account email as Viewer.
4. Save the key and point ga-cli at it in `~/.config/ga-cli/config.toml`:

```toml
default_property = "properties/123456789"
credentials = "~/.config/ga-cli/sa.json"

[properties]           # optional aliases, usable anywhere a property is accepted
blog = "properties/123456789"
site = "properties/987654321"
```

5. Verify end to end: `ga auth check --ping`.

Credential resolution order: `--credentials` > `GA_CREDENTIALS` > config `credentials` >
`GOOGLE_APPLICATION_CREDENTIALS` > application default credentials. The only scope ever
requested is `analytics.readonly`.

Property resolution order: `-P/--property` > `GA_PROPERTY` > config `default_property` >
the sole accessible property (when the credentials can see exactly one).

## Commands

| Command | Purpose |
|---|---|
| `ga report` | Core reporting primitive: metrics, dimensions, ranges, filters, ordering, paging |
| `ga realtime` | Last-30-minutes activity |
| `ga pages` / `ga sources` / `ga events` / `ga trend` | Presets for the most common questions |
| `ga accounts` / `ga properties [list\|get]` | Account and property discovery |
| `ga streams` / `ga custom-dimensions` / `ga custom-metrics` / `ga key-events` | Property metadata |
| `ga meta` | Valid metric/dimension names (including custom fields); never guess names |
| `ga compat` | Check a metric/dimension combination before spending report tokens |
| `ga quota` | Remaining report token quota |
| `ga auth check [--ping]` / `ga auth guide` | Credential verification and setup steps |
| `ga skill install [--project] [--force]` / `show` / `path` | Claude Code skill management |

Full flag reference: [skills/ga-cli/references/commands.md](skills/ga-cli/references/commands.md).

## Output contract

- JSON on stdout is the default. Data goes to stdout; everything else (progress, hints,
  warnings, errors) goes to stderr. stdout carries exactly one JSON document (or one
  table) per invocation, or nothing on error.
- `--compact` for single-line JSON, `--table` for a human table (no compatibility
  guarantee), `GA_AUTO_TABLE=1` renders tables only when stdout is a TTY.
- Report rows are flattened objects: dimension values as strings (date-like dimensions
  normalized to ISO form), metric values coerced to int/float per the declared type.
- Reports return an envelope (`property`, `date_ranges`, `rows`, `row_count`,
  `returned`, `has_more`); `--results-only` emits just the rows array. Complete result
  sets (accounts, properties, streams, ...) are bare arrays; single entities are bare
  objects.
- Command names, flags, env vars, exit codes, and JSON field names are compatibility
  surfaces, frozen at v1.0.0. Breaking any of them is a major-version event.

## Exit codes

| Code | Name | Meaning |
|---|---|---|
| 0 | ok | success (including empty results without `--fail-empty`) |
| 1 | error | unclassified runtime failure |
| 2 | usage | bad flags/args, DSL parse errors, invalid combinations |
| 3 | empty | zero rows and `--fail-empty` was set |
| 4 | auth | no credentials found, or credentials rejected |
| 5 | not_found | property or resource does not exist |
| 6 | permission | credentials valid but lack access |
| 7 | quota | rate limited or property token quota exhausted |
| 8 | retryable | 5xx, network timeout, connection failure |

Agents should branch on codes, not stderr text.

## Filters, ranges, ordering

```bash
-f 'pagePath=^/blog'                     # begins with
-f 'country==United States|Canada'       # in-list (escape a literal pipe as \|)
-f 'sessions>100'                        # metric filter (field is in -m)
--filter-any 'source=@github' --filter-any 'source=@linkedin'   # OR group
-r 7d  -r mtd  -r 2026-06-01:2026-06-15  -r 28daysAgo:yesterday # ranges
--compare prev                           # same-length preceding period
-o -sessions -o pagePath                 # order: -field desc, field asc
```

Operators: `==` `!=` `=@` (contains) `!@` `=^` (begins) `=$` (ends) `=~` (regex) `!~`
`>` `>=` `<` `<=`. String matching is case-insensitive unless `--case-sensitive`.
Anything the DSL cannot express: `--filter-json '<FilterExpression JSON>'` or `@file`.

GA4 standard properties allow roughly 200k core tokens/day, 40k/hour, and 10 concurrent
requests; check live state with `ga quota`. Token cost scales with rows, date range,
and cardinality.

## Claude Code skill

The wheel bundles a Claude Code skill so agents know how to drive the CLI:

| Method | Command |
|---|---|
| Bundled installer (recommended) | `ga skill install` (`--project` for a repo-local install) |
| Homebrew | `brew install sajal2692/tap/ga-cli` then `ga skill install` |
| skills CLI | `npx skills add sajal2692/ga-cli` |
| Manual | `cp -r skills/ga-cli ~/.claude/skills/` |

Reinstall after upgrading the CLI: `ga skill install --force`.

## Development

```bash
uv sync                        # install deps + dev tools
uv run pytest                  # unit, golden, and contract tests
uv run pytest -m e2e           # opt-in live tests (needs GA_E2E=1 + credentials)
uv run ruff check . && uv run mypy
```

Tests never touch the network: the two client factories in `clients.py` are
monkeypatched with fakes returning real proto messages.

## Releasing

1. Update `CHANGELOG.md` and bump `version` in `pyproject.toml`.
2. Tag `vX.Y.Z` and push; `release.yml` runs checks, builds, publishes to PyPI via
   trusted publishing, and creates the GitHub release.
3. Verify `uv tool install ga-cli==X.Y.Z`.
4. Update the Homebrew formula in `sajal2692/homebrew-tap` (bump `url`/`sha256`,
   rerun `brew update-python-resources ga-cli`), then `brew install` smoke test.
5. Verify `ga skill install` from the brew build.
