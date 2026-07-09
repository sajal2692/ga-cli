# Changelog

All notable changes to ga-cli are documented here. The automation contract (command
names, flags, env vars, exit codes, JSON field names) is frozen per major version;
breaking it is a major-version event and is called out explicitly.

## 1.0.1 - 2026-07-09

The command is now **`ga4`** (was `ga`).

- Renamed the console script from `ga` to `ga4`. The bare `ga` collides with the
  oh-my-zsh git plugin's `ga='git add'` alias, which shadowed the binary (and the
  bundled skill's commands) for most users. `ga4` is collision-free and self-describing.
- No other surface changed: the PyPI distribution is still `ga-agent-cli`, the import
  package is still `ga_cli`, the config directory is still `~/.config/ga-cli`, and the
  skill is still installed as `ga-cli`.
- 1.0.0 is yanked on PyPI (it shipped only the shadowed `ga` command). Install 1.0.1.

## 1.0.0 - 2026-07-09 (yanked)

Initial public release. Shipped the command as `ga`; superseded by 1.0.1, which
renames it to `ga4`. Feature set (identical in 1.0.1):

- Reporting: `report` (multi-range, filter DSL, `--filter-json`, ordering,
  offset/limit/`--all` paging, `--totals`, `--quota`, `--compare prev|yoy`,
  `--fail-empty`, `--results-only`, `--raw`), `realtime`, presets `pages`,
  `sources`, `events`, `trend`.
- Discovery: `accounts`, `properties list|get`, `streams`, `custom-dimensions`,
  `custom-metrics`, `key-events`, `meta`, `compat`, `quota`.
- Auth: credential chain (flag > `GA_CREDENTIALS` > config > ADC), `auth check
  [--ping]`, `auth guide`. Read-only scope only.
- Output: flattened JSON rows with typed metrics and ISO dates, envelope with
  `row_count`/`returned`/`has_more`, `--compact`, `--table`, `GA_AUTO_TABLE`.
- Exit code taxonomy 0-8 for agent branching.
- Bundled Claude Code skill with `skill install|show|path`.
