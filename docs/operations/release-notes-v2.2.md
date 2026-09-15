# Akasha v2.2 — release notes

**Any list, any domain.** v2.1's custom list read a spreadsheet you typed — for
books. v2.2 removes the "for books": the connector is domain-declared, so the
same flow works for every library you have. Pick the library first — Books,
Albums, Films, Series, Anime — then drop the file.

**Tagged `v2.2.0`.**

## A note on versioning

`2.2.0` is a feature release with **no breaking change and no owner action**:
`docker compose pull && docker compose up -d`, the same two commands as always.
The pre-upgrade backup still runs on startup. No migration is added (the
proposals table v2.1 created is reused unchanged); existing book lists keep
working byte-for-byte.

## What's new since v2.1.0

- **The library pick comes before the file** (Sprint 084, DEC-160). A list row
  carries no identity, so nothing downstream can route it: the target is a
  single-pick choice made once, before the file can be interpreted. The same
  file for two libraries is two imports; a mixed batch is refused rather than
  guessed.
- **Headers auto-detect in the library's own vocabulary.** Books keep their
  v2.1 word lists exactly; albums add artist words ("Artista" maps the second
  column); films, series and anime declare title words only, and a one-column
  list is valid for them — a missing creator is an empty fact, not an error.
  The screen's column-mapping labels speak the picked library's words (Author,
  Artists, Creators).
- **A confirmed row keeps the cover you saw on its card** (DEC-161 — found by
  the live album walkthrough). Confirming a match now fetches the proposal's
  own cover through the same allowlisted, size-capped path the add screen
  uses, and commit installs it. Previously only books got covers, by the luck
  of the enrichment backfill matching their ISBNs; a MusicBrainz album offers
  no identifier at all, so its cover never arrived. Now it does — for every
  domain, domain-neutrally.
- **Every domain's rows flow through the same proven machinery** — the
  sequential background search, ten proposals per row, Show more, edit and
  re-search, Don't import this row, discard, undo — unchanged and re-proven
  against recorded MusicBrainz captures and a live album import end to end.

## Upgrade

```bash
docker compose pull && docker compose up -d
```

If you pin in `.env`, move the pin:

```bash
echo "AKASHA_VERSION=2.2.0" >> .env   # or track the 2.2 line
docker compose pull && docker compose up -d
```

The board's dev container (built from source) needs no pin — see the runbook.
