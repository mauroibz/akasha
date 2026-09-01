<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/brand/source/mark-on-dark.svg">
  <img src="docs/brand/source/mark-on-light.svg" alt="" width="88" height="88">
</picture>

# Akasha

**A self-hosted library for your thoughts.**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-fbbf24?style=flat-square)](LICENSE)
[![Self-hosted](https://img.shields.io/badge/deploy-LAN%20only-a1a1aa?style=flat-square)](SECURITY.md)
[![Python 3.12](https://img.shields.io/badge/python-3.12-a1a1aa?style=flat-square)](backend/pyproject.toml)
[![React 18](https://img.shields.io/badge/react-18-a1a1aa?style=flat-square)](frontend/package.json)

</div>

<br>

![The Akasha library](docs/brand/screenshots/library.png)

---

## What it is

You add a book, record, anime series, film or television show, score it out of ten, write a note,
put it on a shelf. Reading trackers optimise for other people seeing your opinions and their vendors
selling you stuff; this optimises for you remembering, three years later, whether something was any
good.

Akasha is domain agnostic, it's built so you can extend it to hold information on anything you
enjoy, but today it supports Books, Albums, Anime, Movies and Series. See
[Domains](#domains-and-stack) for more info.

> [!WARNING]
> **v1 has no authentication of any kind.** Anyone who can reach the port can read
> and change everything. Run it on a trusted LAN, never on the public internet.
> See [SECURITY.md](SECURITY.md) for the full threat model.

## What it does

- **One box for multiple domains.** Akasha reaches the web for public APIs
(Open Library, Google Books, MusicBrainz, AniList and Kitsu) to find any piece of media you are
thinking of.
Paste a URL or an ISBN and it resolves that instead of guessing.
- **Record your opinion.** Give it a score out of ten, leave notes if you have them.
Did you drop the book halfway through? Do you want to buy this album in vinyl some day?
Add your item to a shelf and give it a status.
- **Import your library** Importing from existing systems is supported and extensible.
Bring your own Goodreads CSV, a read-only Calibre library or a MyAnimeList export and get your
info migrated.
- **Choose your covers.** If provided by the API, or upload your own, you can choose the how your items look
What you see in the app should reflect what's in your house.
- **Upload your files** While not its primary feature, you can attach files to entries,
in case you need a safe place to store that PDF.

<details>
<summary><b>An entry's detail page</b></summary>

![An album's detail page](docs/brand/screenshots/detail.png)

</details>

## Importing and triage

**Import** brings in a Goodreads CSV export, a Calibre library, a MyAnimeList anime
export, a Letterboxd data export, an IMDb export or a Trakt archive. The screen has two steps:
preview a source and commit it, then work through **Triage**, where committed
rows land as `unsorted` — the ordinary library view hides those until you sort them.
Score edits in Triage save immediately. Each row's status control shows the imported
suggestion, or that domain's default when the source has none — Inbox is already implied
by the screen. Change the target if needed, then apply that row from its check button.
Draft targets survive navigation and refresh within the browser tab until you apply them.

Calibre needs no mount: point it at your library folder and the browser reads it
directly. Only the database and covers upload by default, which keeps the transfer
small; turn on **Also attach the ebook files** to also bring in one file per book. A
library the server can already see can instead be browsed or typed as a path, with no
upload ceiling. Re-running a source is cheap and safe — Akasha uploads only what
changed and never overwrites a value you've edited by hand — and a committed batch can
be undone for 24 hours after commit.

MyAnimeList's gzipped XML export can be uploaded as downloaded or unpacked first. Status,
score, dates, rewatches, watched-episode progress, notes and tags come across; imported anime
then fills its cover, studio, year, season, genres and synopsis from AniList, with Kitsu as a
fallback. This is a snapshot import rather than two-way synchronization.

Letterboxd's export is a .zip of CSVs; upload it exactly as it downloads. Watched films,
ratings, diary entries, reviews, the watchlist and tags come across as one record per film —
half-star ratings double exactly onto Akasha's 1–10, repeated diary rows become rewatches, and
deleted or orphaned entries are deliberately left alone. Films then fill their director,
runtime, countries, languages, genres and cast from Wikidata, and their poster from Stremio's
keyless image service.

An IMDb account exports two shapes — a ratings CSV and a list CSV — and both are read by one
connector, with films and shows routed to their own libraries by their title type and anything
Akasha doesn't hold counted on the preview screen rather than failed. A Trakt export is a .zip
of raw API responses; watched films and shows, ratings, the watchlist and the episode roll-up
come across into both libraries from one archive, with the archive's account settings — which
carry your email address — never opened at all. A show's watched-episode count is its distinct
episodes, rewatches counted once and specials left out, and a show with no watch history falls
back to Trakt's play count and says so on its row.

Connectors are domain-owned and registry-driven; Goodreads and Calibre ship for books,
MyAnimeList for anime, Letterboxd and IMDb for movies, Trakt for movies and series together. A
new one can be added without touching the shared
preview, commit, triage or undo pipeline. See
[how to add a domain and importer](docs/guides/adding-a-domain.md).

## Quick start

You need Docker with the Compose plugin

```bash
git clone https://github.com/mauroibz/akasha.git
cd akasha

cp .env.example .env
$EDITOR .env                              # set USER_AGENT_CONTACT to a real address

mkdir -p calibre
docker compose up -d
```

Open `http://localhost:4441`.

`USER_AGENT_CONTACT` is required — Open Library asks callers to identify themselves,
and startup refuses without it.

`data` and `backups` are named Docker volumes, seeded from the image with the right
ownership already on them. Want them as real host directories instead (a NAS-backed `BACKUP_DIR`, direct access to the sqlite
file)? See [Bind-mounting data and backups](#bind-mounting-data-and-backups).
Want backups on their own disk without moving the database off its named volume? See
[the operator runbook](docs/operations/runbook.md#backups-on-their-own-disk).

### Configuration

Everything is environment variables, all documented in [`.env.example`](.env.example).

| Variable               | Default          | What it does                                                                               |
| ---------------------- | ---------------- | ------------------------------------------------------------------------------------------ |
| `USER_AGENT_CONTACT`   | *required*       | Contact address sent to metadata providers                                                 |
| `GOOGLE_BOOKS_API_KEY` | *empty*          | Optional. Without it, search uses Open Library alone and Spanish-language coverage is poor |
| `TMDB_READ_TOKEN`     | *empty*          | Optional. The movie domain's poster fallback for films with a TMDB id and no IMDb id       |
| `BOOK_TRACKER_ATTACHMENT_MAX_BYTES` | `26214400` (25 MiB) | Per-file cap on attachments                                                       |
| `BOOK_TRACKER_SQLITE_BUSY_TIMEOUT_MS` | `5000`   | How long SQLite waits for a locked database before failing                                 |
| `AKASHA_DATA_VOLUME`   | `akasha_data`    | Docker volume name for the database, covers and attached files                             |
| `AKASHA_BACKUP_VOLUME` | `akasha_backups` | Docker volume name for backups, deliberately outside the data volume                       |
| `CALIBRE_DIR`          | `./calibre`      | Your Calibre library, mounted read-only                                                    |
| `AKASHA_PORT`          | `4441`           | Published port                                                                             |
| `AKASHA_BIND`          | `0.0.0.0`        | Set to `127.0.0.1` to keep it off the network. Publishes on overlay-network interfaces too |
| `AKASHA_VERSION`      | `local`          | Image tag compose runs. Pin a version so rollback is a variable, not a rebuild             |
| `AKASHA_LOG_MAX_SIZE`  | `10m`            | Container log rotation bound, with `AKASHA_LOG_MAX_FILE` (`5`)                             |
| `TZ`                   | `UTC`            | Timezone                                                                                   |
| `LOG_LEVEL`            | `INFO`           | Log verbosity                                                                              |

Check which providers are live:

```bash
curl -s localhost:4441/api/health/providers
```

### Bind-mounting data and backups

`data` and `backups` are named Docker volumes by default. Prefer real host directories
— a NAS-backed `BACKUP_DIR`, or direct host access to the sqlite file? Opt into
[`compose.bind-mounts.yaml`](compose.bind-mounts.yaml), which mounts them as real host
directories instead, with one extra requirement:

```bash
mkdir -p data backups
sudo chown -R 10001:10001 data backups   # the container runs as uid 10001
docker compose -f compose.yaml -f compose.bind-mounts.yaml up -d
```

Use the same two `-f` flags on every later `docker compose` command for this stack.

### Backups

Take one now, or schedule it nightly:

```bash
./scripts/backup.sh                                                       # now
15 3 * * *  cd /srv/akasha && ./scripts/backup.sh >> /var/log/akasha-backup.log 2>&1  # nightly, host crontab
```

Each run backs up the live database through SQLite's own backup API, archives covers,
hardlinks attached files so a week of backups costs about one copy, checksums and
verifies itself, and keeps the last `BACKUP_RETENTION` nights. An upgrade takes its own
backup first and refuses to migrate if it can't.

Restore, rollback and reverse-proxy guidance are in
**[the operator runbook](docs/operations/runbook.md)**.

## Documentation

[`docs/README.md`](docs/README.md) is the map, and says whether each document is
canonical, historical or a proposal. Product behaviour is canonical in the
[product spec](docs/specs/product-spec.md); architecture and contracts in the
[technical spec](docs/specs/technical-spec.md); every material decision, with its
reasoning, in [`docs/decisions.md`](docs/decisions.md). Visual identity — palette,
type, the mark — is in [`docs/brand/`](docs/brand/).

Akasha was built by following the [Seeds](https://github.com/mauroibz/seeds) methodology for agentic development.
The sprint files, decision log and worklog in `docs/` are the real record of that,
mistakes included.

## Development

You need Node 22, npm, and [`uv`](https://docs.astral.sh/uv/). `uv` installs Python
3.12 itself.

```bash
make bootstrap
cp .env.example .env

make dev-backend    # terminal 1 — API at http://localhost:8000
make dev-frontend   # terminal 2 — UI at http://localhost:5173
```

| Command                | What it does                                                                                                                                           |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `make check`           | Format check, lint, types, project state, OpenAPI drift                                                                                                |
| `make test`            | Backend and frontend unit tests                                                                                                                        |
| `make format`          | Apply formatting                                                                                                                                       |
| `make build`           | Python wheel and production SPA                                                                                                                        |
| `make migrate`         | Upgrade the configured database                                                                                                                        |
| `make smoke-container` | Full container proof: healthcheck, non-root, persistence across recreation, every asset chunk, read-only Calibre, backup and restore, graceful SIGTERM |
| `npm run test:e2e`     | Playwright, in `frontend/` — dev server *and* a real production build                                                                                  |

### Domains and stack

FastAPI, SQLAlchemy, Alembic and SQLite on the backend; React 18, Vite, TypeScript,
Tailwind, shadcn/ui and TanStack Query on the frontend. One container, one process,
one SQLite file.

A **domain** is a kind of thing the library holds — a book, an album, an anime series, a film,
a television series.
Each lives in its own package under `backend/src/book_tracker/domains/`, declaring its fields, statuses,
formats, identity rule and provider; that declaration is served over the API and every
screen renders from it, so nothing above the registry branches on type. Adding one
costs a package, a registry entry and provider wiring: no migration, no edit to
another domain's files. See **[how to add a domain](docs/guides/adding-a-domain.md)**,
binding contract in [technical spec §6.6](docs/specs/technical-spec.md).

## Contributing

Issues and pull requests are welcome. **[`CONTRIBUTING.md`](CONTRIBUTING.md)** has the
setup and the gates. Provider fixtures in `backend/tests/fixtures/providers/` are
pinned recordings of real API responses — never re-record one to make a test pass,
that turns a regression test into a rubber stamp.

## License

[GNU AGPL v3](LICENSE). Run, modify and share Akasha freely, including inside an
institution. Redistributing it, or running a modified version as a network service,
requires publishing your source under the same licence — for hosting or redistribution
without that obligation, see [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md).
