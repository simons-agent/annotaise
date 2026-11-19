#!/usr/bin/env bash
# Restore one AnnotAISE instance's database from a backup.sh dump.
#
#   deploy/privdev/restore.sh annotaise-test ~/annotaise/backups/annotaise-test/<stamp>.dump
#
# DESTRUCTIVE: stops the stack, removes the instance's Postgres volume,
# recreates an empty database and loads the dump with pg_restore, then starts
# the whole stack again. Uses $COMPOSE (default "docker compose"; e.g.
# COMPOSE="podman compose"). Take a fresh backup.sh first if the current data matter.
set -euo pipefail

project="${1:?usage: restore.sh <annotaise-test|annotaise-study> <dump>}"
dump="${2:?path to a pg_dump -Fc file}"
case "$project" in
  annotaise-test|annotaise-study) ;;
  *) echo "unknown project: $project" >&2; exit 2 ;;
esac
[ -f "$dump" ] || { echo "no such dump: $dump" >&2; exit 2; }
[ "$(head -c 5 "$dump")" = "PGDMP" ] || { echo "not a custom-format dump: $dump" >&2; exit 2; }

repo="$(cd "$(dirname "$0")/../.." && pwd)"
read -r -a COMPOSE_CMD <<< "${COMPOSE:-docker compose}"
engine="${COMPOSE_CMD[0]}"   # docker or podman: same volume/exec CLI
compose=("${COMPOSE_CMD[@]}" -p "$project" --project-directory "$repo"
  -f "$repo/docker-compose.yaml" -f "$repo/deploy/privdev/compose.override.yaml"
  --env-file "$repo/deploy/privdev/$project/.env")

echo "stopping $project"
"${compose[@]}" stop
"${compose[@]}" rm -f db
echo "removing volume ${project}_pg_annotaise"
"$engine" volume rm "${project}_pg_annotaise"

"${compose[@]}" up -d --no-deps db
echo "waiting for postgres"
for _ in $(seq 1 60); do
  # The image's init runs a temporary server first; wait for the final one.
  if "${compose[@]}" exec -T db sh -c 'pg_isready -q -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'; then break; fi
  sleep 2
done
"${compose[@]}" exec -T db sh -c 'pg_isready -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'

echo "pg_restore $dump"
"${compose[@]}" exec -T db sh -c 'pg_restore --exit-on-error --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$dump"

echo "starting $project"
"${compose[@]}" up -d
echo "restore of $project complete"
