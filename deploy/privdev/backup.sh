#!/usr/bin/env bash
# Nightly PostgreSQL backup for one AnnotAISE instance.
#
#   deploy/privdev/backup.sh annotaise-test
#   deploy/privdev/backup.sh annotaise-study
#
# Writes `pg_dump -Fc` to
#   /srv/projects/annotaise/runtime/backups/<project>/<UTC timestamp>.dump
# and prunes old dumps, keeping the newest dump of each of the 14 most recent
# days and the newest dump of each of the 8 most recent ISO weeks.
# No credentials are needed on the host: pg_dump runs inside the db container
# over its local socket, using the container's POSTGRES_USER / POSTGRES_DB.
set -euo pipefail
umask 077

project="${1:?usage: backup.sh <annotaise-test|annotaise-study>}"
case "$project" in
  annotaise-test|annotaise-study) ;;
  *) echo "unknown project: $project" >&2; exit 2 ;;
esac

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
out="$dir/$stamp.dump"
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
python3 - "$dir" "$keep_daily" "$keep_weekly" <<'PY'
import datetime as dt
import pathlib
import sys

directory, keep_daily, keep_weekly = pathlib.Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
dumps = []
for path in directory.glob("*.dump"):
    try:
        stamp = dt.datetime.strptime(path.stem, "%Y%m%dT%H%M%SZ")
    except ValueError:
        continue  # not ours; leave it alone
    dumps.append((stamp, path))
dumps.sort(reverse=True)  # newest first

keep, days, weeks = set(), [], []
for stamp, path in dumps:
    day = stamp.date()
    week = stamp.isocalendar()[:2]
    if day not in days and len(days) < keep_daily:
        days.append(day)
        keep.add(path)
    if week not in weeks and len(weeks) < keep_weekly:
        weeks.append(week)
        keep.add(path)

for _, path in dumps:
    if path not in keep:
        path.unlink()
        print(f"pruned {path.name}")
print(f"retained {len(keep)} dump(s) in {directory}")
PY
