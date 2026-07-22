#!/usr/bin/env bash
set -euo pipefail

smoke_data="$(mktemp -d /tmp/akasha-smoke.XXXXXX)"
chmod 0777 "$smoke_data"
container_name="akasha-sprint-001-smoke"
cleanup() {
  docker rm -f "$container_name" >/dev/null 2>&1 || true
  rm -rf "$smoke_data"
}
trap cleanup EXIT

docker build --tag akasha:sprint-001 .
docker run --detach --name "$container_name" --publish 127.0.0.1::8000 \
  --volume "$smoke_data:/data" --env USER_AGENT_CONTACT=smoke@example.invalid akasha:sprint-001 >/dev/null

wait_until_ready() {
  for _ in $(seq 1 30); do
    if docker exec "$container_name" python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/ready')" >/dev/null 2>&1; then return 0; fi
    sleep 1
  done
  docker logs "$container_name"
  return 1
}

wait_until_ready
docker exec "$container_name" python -c "import sqlite3; db=sqlite3.connect('/data/books.db'); db.execute('INSERT INTO schema_probe(id) VALUES (101)'); db.commit()"
test "$(docker exec "$container_name" id -u)" != "0"
if docker exec "$container_name" sh -c "command -v node"; then echo "Node exists in runtime image"; exit 1; fi
docker rm -f "$container_name" >/dev/null
docker run --detach --name "$container_name" --volume "$smoke_data:/data" \
  --env USER_AGENT_CONTACT=smoke@example.invalid akasha:sprint-001 >/dev/null
wait_until_ready
docker exec "$container_name" python -c "import sqlite3; db=sqlite3.connect('/data/books.db'); assert db.execute('SELECT id FROM schema_probe WHERE id=101').fetchone() == (101,)"
docker exec "$container_name" python -c "import urllib.request; assert b'Akasha' in urllib.request.urlopen('http://127.0.0.1:8000/books/101').read()"
echo "Container smoke test passed: ready, SPA, persistence, non-root, and no Node."
