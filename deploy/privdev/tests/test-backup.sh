#!/usr/bin/env bash
# Offline tests for deploy/privdev/backup.sh: label parsing and retention.
# Needs only bash and python3 (no docker, no database).
#
#   bash deploy/privdev/tests/test-backup.sh
set -euo pipefail

here="$(cd "$(dirname "$0")/.." && pwd)"
backup="$here/backup.sh"
prune="$here/prune-backups.py"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
fail=0
check() {  # check <description> <command...>
  local what="$1"; shift
  if "$@"; then echo "ok   $what"; else echo "FAIL $what"; fail=1; fi
}

# --- label parsing (rejected before any docker call) ---
status() { set +e; "$@" >/dev/null 2>&1; local s=$?; set -e; echo "$s"; }
check "bad label is rejected (exit 2)" \
  test "$(status bash "$backup" annotaise-test --label 'Pre/Deploy')" = 2
check "empty label is rejected (exit 2)" \
  test "$(status bash "$backup" annotaise-test --label '')" = 2
check "unknown option is rejected (exit 2)" \
  test "$(status bash "$backup" annotaise-test --bogus)" = 2
check "unknown project is rejected (exit 2)" \
  test "$(status bash "$backup" nope --label predeploy)" = 2

check "missing ANNOTAISE_BACKUP_ROOT is rejected (exit 2)" \
  test "$(status env -u ANNOTAISE_BACKUP_ROOT bash "$backup" annotaise-test)" = 2

# --- retention: same-day dumps pruned, labelled dumps never ---
dir="$work/annotaise-study"
mkdir -p "$dir"
for name in \
  20261119T021132Z-predeploy 20261119T023500Z 20261119T010000Z \
  20261118T023000Z 20261118T120000Z 20260101T000000Z-predeploy \
  20250101T000000Z notes; do
  : > "$dir/$name.dump"
done
python3 "$prune" "$dir" 14 8 > "$work/prune.log"

check "labelled same-day pre-deploy dump kept" test -e "$dir/20261119T021132Z-predeploy.dump"
check "old labelled dump kept" test -e "$dir/20260101T000000Z-predeploy.dump"
check "newest dump of the day kept" test -e "$dir/20261119T023500Z.dump"
check "older dump of the same day pruned" test ! -e "$dir/20261119T010000Z.dump"
check "newest dump of previous day kept" test -e "$dir/20261118T120000Z.dump"
check "older dump of previous day pruned" test ! -e "$dir/20261118T023000Z.dump"
check "foreign file left alone" test -e "$dir/notes.dump"
check "labelled dumps reported as kept" grep -q "kept 2 labelled dump(s)" "$work/prune.log"

exit "$fail"
