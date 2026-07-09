# Changelog

All notable changes to ga-cli are documented here. The automation contract (command
names, flags, env vars, exit codes, JSON field names) is frozen per major version;
breaking it is a major-version event and is called out explicitly.

## 1.0.0 - 2026-07-09

Initial public release.

- Reporting: `ga report` (multi-range, filter DSL, `--filter-json`, ordering,
  offset/limit/`--all` paging, `--totals`, `--quota`, `--compare prev|yoy`,
  `--fail-empty`, `--results-only`, `--raw`), `ga realtime`, presets `ga pages`,
  `ga sources`, `ga events`, `ga trend`.
- Discovery: `ga accounts`, `ga properties list|get`, `ga streams`,
  `ga custom-dimensions`, `ga custom-metrics`, `ga key-events`, `ga meta`,
  `ga compat`, `ga quota`.
- Auth: credential chain (flag > `GA_CREDENTIALS` > config > ADC), `ga auth check
  [--ping]`, `ga auth guide`. Read-only scope only.
- Output: flattened JSON rows with typed metrics and ISO dates, envelope with
  `row_count`/`returned`/`has_more`, `--compact`, `--table`, `GA_AUTO_TABLE`.
- Exit code taxonomy 0-8 for agent branching.
- Bundled Claude Code skill with `ga skill install|show|path`.
