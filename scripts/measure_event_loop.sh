#!/usr/bin/env bash
#
# Sprint 059, Phase A: run scripts/measure_event_loop.py's three scenarios against
# the real production image, CPU-constrained the way a home server actually is,
# rather than on this workstation's full core count. Builds the same Dockerfile
# `ci.yml`'s `container` job and `scripts/smoke_container.sh` already exercise —
# there is still only one image definition.
#
# Usage: scripts/measure_event_loop.sh [cpus] [scenario ...]
#   cpus      docker's --cpus value (default 2 — this repository's own precedent
#             for "constrained like a shared/small runner", set when the e2e CI
#             flakiness fix reproduced GitHub's runners with `taskset -c 0,1`).
#   scenario  one or more of: import covers attachment (default: all three).
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

cpus="${1:-2}"
shift || true
scenarios=("$@")
if [ "${#scenarios[@]}" -eq 0 ]; then
  scenarios=(import covers attachment)
fi

image="akasha:eventloop-$$"
echo "== building $image =="
docker build -t "$image" -f Dockerfile . >/tmp/akasha-eventloop-build.log 2>&1 ||
  { tail -60 /tmp/akasha-eventloop-build.log; exit 1; }

overall=0
for scenario in "${scenarios[@]}"; do
  container="akasha-eventloop-$$-$scenario"
  port="$(python3 -c 'import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()')"
  echo
  echo "== $scenario : starting $container on 127.0.0.1:$port, --cpus=$cpus =="
  docker run -d --rm \
    --name "$container" \
    --cpus="$cpus" \
    -p "127.0.0.1:${port}:8000" \
    -e "USER_AGENT_CONTACT=event-loop-benchmark@example.invalid" \
    "$image" >/dev/null

  cleanup() { docker stop "$container" >/dev/null 2>&1 || true; }
  trap cleanup EXIT

  # Docker does not evaluate HEALTHCHECK failures during the Dockerfile's 60s
  # start-period — a scenario that runs (and finishes) inside that window can
  # never observe a real "unhealthy" transition, which would silently pass
  # criterion 5 for the wrong reason. Wait for the first real evaluation
  # (status leaves "starting") before the timed scenario begins.
  echo "waiting for the container's own healthcheck to leave its start-period..."
  for _ in $(seq 1 90); do
    status="$(docker inspect --format '{{.State.Health.Status}}' "$container" 2>/dev/null || echo "")"
    [ "$status" != "starting" ] && [ -n "$status" ] && break
    sleep 1
  done
  echo "healthcheck status before the scenario: ${status:-unknown}"

  (
    cd backend
    UV_CACHE_DIR=/tmp/akasha-uv-cache uv run python ../scripts/measure_event_loop.py \
      --base-url "http://127.0.0.1:${port}" \
      --scenario "$scenario" \
      --cpus "$cpus" \
      --container "$container"
  ) || overall=1

  docker stop "$container" >/dev/null 2>&1 || true
  trap - EXIT
done

docker rmi "$image" >/dev/null 2>&1 || true

echo
if [ "$overall" -eq 0 ]; then
  echo "ALL SCENARIOS WITHIN BUDGET (--cpus=$cpus)"
else
  echo "AT LEAST ONE SCENARIO OVER BUDGET OR UNHEALTHY (--cpus=$cpus)"
fi
exit "$overall"
