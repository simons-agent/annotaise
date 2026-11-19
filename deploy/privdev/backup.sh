#!/usr/bin/env bash
# Nightly PostgreSQL backup for one AnnotAISE instance.
#
#   deploy/privdev/backup.sh annotaise-test
#   deploy/privdev/backup.sh annotaise-study
#   deploy/privdev/backup.sh annotaise-study --label predeploy   # before a redeploy
#
# Writes `pg_dump -Fc` to
#   /srv/projects/annotaise/runtime/backups/<project>/<UTC timestamp>.dump
# (or <UTC timestamp>-<label>.dump with --label) and prunes old unlabelled
# dumps, keeping the newest dump of each of the 14 most recent days and the
# newest dump of each of the 8 most recent ISO weeks. Labelled dumps are never
# pruned (see prune-backups.py); delete them by hand when no longer needed.
# No credentials are needed on the host: pg_dump runs inside the db container
# over its local socket, using the container's POSTGRES_USER / POSTGRES_DB.
set -euo pipefail
umask 077

usage="usage: backup.sh <annotaise-test|annotaise-study> [--label <a-z0-9->]"
project="${1:?$usage}"
shift
case "$project" in
  annotaise-test|annotaise-study) ;;
  *) echo "unknown project: $project" >&2; exit 2 ;;
esac
label=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --label)
      [ "$#" -ge 2 ] || { echo "$usage" >&2; exit 2; }
      label="$2"
      [[ "$label" =~ ^[a-z0-9][a-z0-9-]*$ ]] || { echo "bad label: '$label' (use a-z, 0-9, -)" >&2; exit 2; }
      shift 2 ;;
    *) echo "$usage" >&2; exit 2 ;;
  esac
done

backup_root="${ANNOTAISE_BACKUP_ROOT:-/srv/projects/annotaise/runtime/backups}"
dir="$backup_root/$project"
keep_daily="${KEEP_DAILY:-14}"
keep_weekly="${KEEP_WEEKLY:-8}"

container="$(docker ps -q \
  --filter "label=com.docker.compose.project=$project" \
  --filter "label=com.docker.compose.service=db")"
[ -n "$container" ] || { echo "no running db container for $project" >&2; exit 1; }

mkdir -p "$dir"
chmod 0700 "$dir"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="$dir/$stamp${label:+-$label}.dump"
tmp="$dir/.$stamp.dump.partial"

trap 'rm -f "$tmp"' EXIT
docker exec "$container" sh -c 'pg_dump -Fc -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > "$tmp"
# Sanity check: a custom-format dump starts with "PGDMP" and lists its TOC.
[ "$(head -c 5 "$tmp")" = "PGDMP" ] || { echo "dump is not custom format" >&2; exit 1; }
docker exec -i "$container" pg_restore --list < "$tmp" > /dev/null
mv "$tmp" "$out"
trap - EXIT
echo "backup $project -> $out ($(stat -c %s "$out") bytes)"

# Retention: keep newest per day (14 days) and newest per ISO week (8 weeks).
# Labelled dumps (<stamp>-<label>.dump) are never pruned; remove them by hand.
python3 "$(dirname "$(readlink -f "$0")")/prune-backups.py" "$dir" "$keep_daily" "$keep_weekly"
