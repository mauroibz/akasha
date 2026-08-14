# Akasha v1.1 — release notes

Post-v1 work, from Sprint 019 through Sprint 024. v1 is unchanged in what it
promises; this release adds attachments, better metadata, a sortable creator
name, and a way to get your library back out.

**Tagged `v1.1.0`** at the close of Sprint 024.

## A note on versioning

There is no versioning policy yet, and this is the first release to need one.
`1.1.0` was chosen to read the obvious way — a feature release on top of `v1.0.0`,
breaking nothing — rather than to satisfy a rule that does not exist. Two things
are worth writing down before a policy is invented:

- **The package metadata had drifted.** `backend/pyproject.toml`,
  `frontend/package.json` and the FastAPI `version` all still said `0.1.0` while
  the repository carried a `v1.0.0` tag, because v1 was tagged without bumping
  them. All three now say `1.1.0`, so the tag and the packages agree for the
  first time. The jump skips `1.0.0` in package metadata deliberately; the tag
  is the authority for what v1 was.
- **The FastAPI version string is part of the API contract.** It lands in
  `frontend/openapi.json`, so bumping it regenerates that file and the frontend
  type check is what catches a forgotten regeneration.

## What's new since v1.0.0

- **Export** (Sprint 024). `GET /api/export` streams the whole library as
  entity-shaped JSON — `type`, identifiers and an opaque `metadata` object —
  and `?format=csv` gives a Goodreads-shaped CSV that opens in a spreadsheet.
  What you typed survives; what the application derived is deliberately absent,
  so a later reader cannot mistake a cache for authority. Attachments travel as
  references plus their sha256 rather than bytes, which keeps the export a file
  you can read instead of a multi-gigabyte archive — and the digest still
  resolves, because a blob's path *is* its digest.
- **Creator sort names** (Sprint 023). The library sorts by the name a creator
  files under, not the name it displays under, so García Márquez sits under G
  and Bioy Casares under B. Calibre's curated sort names seed it where they
  exist, and any name can be corrected by hand — the correction is yours and is
  never recomputed over.
- **Attachments, and their lifecycle** (Sprints 021–022). Attach a file to an
  edition, rename it, remove it with a confirmation. Files are stored by content,
  so the same file attached twice costs one copy and seven nights of backups
  cost about one more. `akasha-attachments reclaim` collects blobs nothing
  references, dry-run by default.
- **Metadata completeness** (Sprint 020). Choose a cover from the editions
  actually published, at no extra request cost, with a provider-agnostic daily
  quota guard behind it. The measurement that preceded it also killed a broader
  cross-provider merge that would have bought a description 22% of the time
  while breaching a free tier.
- **Post-v1 polish** (Sprint 019). Score chips read as filled chips, `s` works
  on `/triage`, and a committed import no longer looks like it did nothing.

## Known and left

- **There is no export button in the UI.** The route is the surface; you need
  the URL. No screen in the product spec asks for one, so none was invented.
- One dev-library item carries an Open Library author key in place of an author
  name and sorts under O.
- `HEAD` on any route returns 405, application-wide.
- "Replace cover" on the detail page is an unstyled file input.
- The orphaned *cover* file is still not collected. The reclaim is scoped to
  attachments on purpose, because a cover is cache the application can re-fetch.

## Still true from v1

No authentication. **LAN only** — no public DNS, port forwarding, tunnel, or
internet-reachable proxy until authentication exists. The nightly database
backup remains non-optional in production: export is a portability story, not a
restore story.
