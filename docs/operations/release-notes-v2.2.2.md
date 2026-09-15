# Akasha v2.2.2 — release notes

**The import screen, tidied.** v2.2.2 is the polish pass on v2.2/v2.2.1's list
importer, straight from validating it in daily use:

- **The importer strip is a quiet row of cards.** Each connector is a
  two-line card — its name in the reading voice, the library it serves as a
  plain caption beneath — with the active card raised rather than filled in.
  No pill chrome, no colored chips.
- **The column mapping is one aligned grid.** The separator pick, the title
  and creators column numbers, and the no-creators checkbox share two
  baselines: labels on one line, same-height controls on the next. Two
  columns on a phone, one tidy row on a desktop.
- **A chosen separator is the final word.** Auto-detect stays the default;
  pick comma, semicolon or tab and the reader obeys — refusing anything
  else by name, and treating the same file read with two separators as two
  separate imports.
- **A sample row shows the config working.** One line beneath the mapping
  splits your first data row on the chosen (or sniffed) separator, live,
  before anything is sent. Display only — Preview stays the truth.
- **And CI stops crying wolf.** The one genuinely flaky test class (a
  frame-timing probe on shared runners) now has a named, budgeted policy
  instead of intermittent red runs: generous budgets where the probe needs
  them, fail-fast everywhere else. No bound was loosened.

**Tagged `v2.2.2`.** Patch release: no breaking change, no owner action, no
migration.

## Upgrade

```bash
docker compose pull && docker compose up -d
```

If you pin in `.env`, move the pin to `AKASHA_VERSION=2.2.2` (or track the
`2.2` line).
