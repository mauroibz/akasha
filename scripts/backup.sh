#!/usr/bin/env bash
#
# Nightly Akasha backup, run from the host scheduler.
#
# The application container is not a cron daemon and must not become one, so this
# script belongs in the host's crontab (see docs/operations/runbook.md):
#
#   15 3 * * *  cd /srv/akasha && ./scripts/backup.sh >> /var/log/akasha-backup.log 2>&1
#
# The backup is taken *through the running container* on purpose. It is an online
# backup of a live SQLite database, which needs the same sqlite build that is
# writing to it, and it means the host needs nothing installed but docker.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

service="${AKASHA_SERVICE:-akasha}"
keep="${BACKUP_RETENTION:-7}"
label="${BACKUP_LABEL:-nightly}"

if ! docker compose ps --status running --services 2>/dev/null | grep -qx "$service"; then
  echo "error: the '$service' service is not running." >&2
  echo "An online backup reads from the live database, so start the stack first:" >&2
  echo "  docker compose up -d" >&2
  exit 1
fi

docker compose exec -T "$service" \
  akasha-backup create --data-dir /data --dest /backups --label "$label" --keep "$keep"
