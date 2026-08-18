#!/usr/bin/env bash
#
# Compose smoke test: the deployed artifact, exercised the way it is deployed.
#
# This drives `docker compose` rather than bare `docker run` because the thing
# being tested is the documented deployment, mounts and recreation included.
# data/backups are throwaway named volumes, unique to this run; calibre is a
# throwaway directory under /tmp. The owner's own volumes and ./data are never
# touched.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

workdir="$(mktemp -d /tmp/akasha-smoke.XXXXXX)"
export COMPOSE_PROJECT_NAME="akasha-smoke"
export CALIBRE_DIR="$workdir/calibre"
export USER_AGENT_CONTACT="smoke@example.invalid"
# The `name:` override in compose.yaml's top-level `volumes:` makes the Docker
# volume name literal, which bypasses Compose's usual project-prefix collision
# protection — so a run-unique name is this script's job, not Compose's.
run_id="$(basename "$workdir")"
export AKASHA_DATA_VOLUME="akasha-smoke-${run_id}-data"
export AKASHA_BACKUP_VOLUME="akasha-smoke-${run_id}-backups"
# AC4 later re-points $AKASHA_DATA_VOLUME at a restored volume; keep the
# original name so cleanup can still find and remove it.
data_volume_original="$AKASHA_DATA_VOLUME"
export GOOGLE_BOOKS_API_KEY=""
export AKASHA_BIND="127.0.0.1"
AKASHA_PORT="$(python3 -c 'import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()')"
export AKASHA_PORT

restored_volume=""

cleanup() {
  docker compose down --remove-orphans --timeout 10 >/dev/null 2>&1 || true
  docker volume rm -f "$data_volume_original" "$AKASHA_BACKUP_VOLUME" >/dev/null 2>&1 || true
  [ -z "$restored_volume" ] || docker volume rm -f "$restored_volume" >/dev/null 2>&1 || true
  # calibre is a real host bind mount, host-owned throughout and mounted :ro,
  # so nothing under it is ever container-written.
  rm -rf "$workdir"
}
trap cleanup EXIT

step() { printf '\n== %s ==\n' "$*"; }
fail() { printf 'FAIL: %s\n' "$*" >&2; docker compose logs --no-color akasha >&2 || true; exit 1; }
api() { curl -fsS --max-time 20 "http://127.0.0.1:${AKASHA_PORT}$1" "${@:2}"; }

mkdir -p "$CALIBRE_DIR/Personal"

python3 - "$CALIBRE_DIR/Personal/metadata.db" <<'PY'
import sqlite3
import sys

connection = sqlite3.connect(sys.argv[1])
connection.executescript(
    """
    CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT, pubdate TEXT, path TEXT, uuid TEXT);
    CREATE TABLE authors (id INTEGER PRIMARY KEY, name TEXT);
    CREATE TABLE books_authors_link (book INTEGER, author INTEGER);
    CREATE TABLE identifiers (book INTEGER, type TEXT, val TEXT);
    INSERT INTO books VALUES (1, 'El Aleph', '1949-01-01', 'Borges/El Aleph (1)', 'u-1');
    INSERT INTO authors VALUES (1, 'Jorge Luis Borges');
    INSERT INTO books_authors_link VALUES (1, 1);
    INSERT INTO identifiers VALUES (1, 'isbn', '9788420633114');
    """
)
connection.commit()
connection.close()
PY

wait_healthy() {
  local container status
  container="$(docker compose ps -q akasha)"
  [ -n "$container" ] || fail "no akasha container is running"
  for _ in $(seq 1 90); do
    status="$(docker inspect --format '{{.State.Health.Status}}' "$container")"
    case "$status" in
      healthy) return 0 ;;
      unhealthy) fail "the container reported itself unhealthy" ;;
    esac
    sleep 1
  done
  fail "the container never became healthy"
}

step "Build the image"
docker compose build --quiet

step "Start the stack"
docker compose up --detach --wait=false >/dev/null
# Assert the image's own HEALTHCHECK, not a poll of our own invention: a broken
# healthcheck is invisible to a test that reimplements it.
wait_healthy

step "AC1: no Node runtime, non-root user"
[ "$(docker compose exec -T akasha id -u)" != "0" ] || fail "the container runs as root"
if docker compose exec -T akasha sh -c 'command -v node' >/dev/null 2>&1; then
  fail "Node is present in the runtime image"
fi

step "Write an entry, a score and a note through the API"
# A manual add needs an idempotency key or an ISBN. The key also makes this
# step safe to re-run against a data directory that already has the entry.
created="$(api /api/entries -H 'content-type: application/json' -d '{
  "manual": {"title": "Ficciones", "authors": ["Jorge Luis Borges"], "year": 1944},
  "status": "read",
  "score": 9,
  "idempotency_key": "smoke-ficciones"
}')"
entry_id="$(printf '%s' "$created" | python3 -c 'import json,sys; print(json.load(sys.stdin)["entry"]["id"])')"
api "/api/entries/$entry_id" -X PATCH -H 'content-type: application/json' \
  -d '{"notes": "Kept for the Aleph, reread for the maps."}' >/dev/null

read_back() {
  api "/api/entries/$entry_id" | python3 -c '
import json
import sys

entry = json.load(sys.stdin)
print(entry["item"]["title"], entry["score"], entry["notes"], sep="|")
'
}
expected="Ficciones|9|Kept for the Aleph, reread for the maps."
[ "$(read_back)" = "$expected" ] || fail "the entry did not read back: $(read_back)"

step "AC1: every emitted chunk is served (DEC-037 splits the bundle)"
index="$(api /)"
assets="$(printf '%s' "$index" | grep -oE '/assets/[A-Za-z0-9._-]+\.(js|css)' | sort -u)"
[ -n "$assets" ] || fail "index.html referenced no assets at all"

# A missing chunk does NOT 404: the SPA catch-all answers every unmatched path
# with index.html and a 200, so checking the status code here would prove
# nothing at all. The content type is what distinguishes a served asset from
# the shell standing in for one.
content_type_of() {
  curl -fsS --max-time 20 -o /dev/null -w '%{content_type}' "http://127.0.0.1:${AKASHA_PORT}$1"
}
case "$(content_type_of /assets/deliberately-missing.js)" in
  text/html*) : ;;
  *) fail "the SPA fallback changed; this check no longer distinguishes a missing chunk" ;;
esac
for asset in $assets; do
  case "$asset:$(content_type_of "$asset")" in
    *.js:text/javascript*|*.css:text/css*) : ;;
    *) fail "asset $asset was answered by the SPA shell instead of being served" ;;
  esac
done
printf 'served %s asset(s), each with its own content type\n' "$(printf '%s\n' "$assets" | wc -l)"

step "SPA deep link falls through to the shell"
api "/books/$entry_id" | grep -q "Akasha" || fail "a deep SPA route did not return the shell"

step "AC2: /calibre is read-only at the mount and in code"
if docker compose exec -T akasha sh -c 'touch /calibre/breakin' >/dev/null 2>&1; then
  fail "the Calibre mount accepted a write"
fi
docker compose exec -T akasha python -c '
from pathlib import Path

from book_tracker.domains.book.calibre import CalibreAdapter

snapshot = CalibreAdapter(Path("/calibre")).read("Personal")
assert [record["title"] for record in snapshot.records] == ["El Aleph"], snapshot.records
print("calibre read through the adapter, query_only enforced")
' || fail "the Calibre adapter could not read the read-only mount"

step "AC3: backup, verify, and restore into an empty directory"
BACKUP_RETENTION=7 ./scripts/backup.sh
backup_name="$(docker compose exec -T akasha sh -c 'ls /backups | grep ^nightly- | tail -1' | tr -d '\r')"
[ -n "$backup_name" ] || fail "the backup script wrote nothing"
docker compose exec -T akasha akasha-backup verify "/backups/$backup_name"
docker compose exec -T akasha akasha-backup restore "/backups/$backup_name" --into /tmp/restore-drill
docker compose exec -T akasha python -c '
import sqlite3

database = sqlite3.connect("/tmp/restore-drill/books.db")
row = database.execute("SELECT i.title, e.score, e.notes FROM entries e JOIN items i ON i.id = e.item_id").fetchone()
database.close()
assert row == ("Ficciones", 9, "Kept for the Aleph, reread for the maps."), row
print("restored:", row)
' || fail "the restored database did not hold the values that were written"

step "AC4: named-volume restore drill (runbook procedure)"
# AC3 restores inside the already-running container's own filesystem. This
# exercises the documented host-side path instead: a bare `docker run` against
# the named volumes, and the AKASHA_DATA_VOLUME flip that runbook.md's
# "Restoring" section describes.
docker compose down --timeout 10 >/dev/null
restored_volume="${AKASHA_DATA_VOLUME}-restored"
docker volume create "$restored_volume" >/dev/null
docker run --rm --user 10001 \
  -v "$AKASHA_BACKUP_VOLUME:/backups:ro" -v "$restored_volume:/data" \
  akasha:local akasha-backup restore "/backups/$backup_name" --into /data
export AKASHA_DATA_VOLUME="$restored_volume"
docker compose up --detach --wait=false >/dev/null
wait_healthy
[ "$(read_back)" = "$expected" ] || fail "the restored volume did not survive the flip: $(read_back)"

step "AC2: data survives docker compose down && up"
docker compose down --timeout 10 >/dev/null
docker compose up --detach --wait=false >/dev/null
wait_healthy
[ "$(read_back)" = "$expected" ] || fail "the entry did not survive recreation: $(read_back)"

step "Signals: SIGTERM stops the container promptly and cleanly"
container="$(docker compose ps -q akasha)"
started="$(date +%s)"
docker compose stop --timeout 10 >/dev/null
elapsed="$(( $(date +%s) - started ))"
exit_code="$(docker inspect --format '{{.State.ExitCode}}' "$container")"
[ "$exit_code" != "137" ] || fail "the container was SIGKILLed after ignoring SIGTERM"
[ "$elapsed" -lt 10 ] || fail "the container took ${elapsed}s to stop"
# The exit code alone proves little: compose runs the image under tini, which
# reports 128+SIGTERM even for a clean stop. What matters is that the
# application ran its own shutdown, so the job runner was cancelled and SQLite
# was closed rather than killed mid-write.
# `docker compose stop` returns before the log driver has necessarily flushed
# the container's final lines, so a single grep here races the shutdown it is
# trying to observe: CI has seen this fail with the line arriving 80ms later.
shutdown_logged=""
for _ in $(seq 1 30); do
  if docker compose logs --no-color akasha 2>&1 | grep -q "Application shutdown complete"; then
    shutdown_logged="yes"
    break
  fi
  sleep 1
done
[ -n "$shutdown_logged" ] || fail "the application did not run a graceful shutdown"
printf 'stopped in %ss with exit code %s, shutdown was graceful\n' "$elapsed" "$exit_code"

printf '\nContainer smoke test passed: healthcheck, non-root, no Node, API persistence across\n'
printf 'recreation, every emitted chunk served, read-only Calibre, an in-container restore,\n'
printf 'and a named-volume restore drill through the documented host-side procedure.\n'
