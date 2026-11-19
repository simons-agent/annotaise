#!/usr/bin/env bash
# Offline tests that the deploy kit is host-agnostic: no AgentBox paths or
# names, compose/exec only through $COMPOSE (Podman-ready), write-env.sh
# output, and the dataset timer units. Needs bash and python3 only.
#
#   bash deploy/privdev/tests/test-portable.sh
set -euo pipefail

here="$(cd "$(dirname "$0")/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
fail=0
check() {  # check <description> <command...>
  local what="$1"; shift
  if "$@"; then echo "ok   $what"; else echo "FAIL $what"; fail=1; fi
}

# --- no AgentBox specifics in tracked files (README examples and the
#     container-internal /srv/static path of the gateway are exempt) ---
scan() (
  cd "$here"
  local f hits=1
  while IFS= read -r f; do
    case "$f" in README.md|tests/test-portable.sh) continue ;; esac
    if sed 's#/srv/static#STATIC#g' "$f" | grep -nEi '/srv/|agentbox|tail289ef2'; then
      echo "  ^ in $f"; hits=0
    fi
  done < <(git ls-files -c -o --exclude-standard . | sort -u)
  [ "$hits" = 1 ]
)
check "no /srv/, agentbox or tailnet name outside README" scan

# --- compose and exec only through $COMPOSE ---
bare_docker() {
  # code lines (not comments) that call docker directly
  ! grep -nE '^[^#]*(^|[^A-Za-z_.-])docker (ps|exec|volume|run|compose)\b' "$here"/*.sh \
    | grep -v 'COMPOSE:-docker compose'
}
check "no bare docker call in deploy/privdev/*.sh" bare_docker
check "scripts honour COMPOSE" grep -q 'COMPOSE:-docker compose' "$here/backup.sh" "$here/restore.sh"

# --- write-env.sh: portable, 0600, empty SMTP password ---
envdir="$work/env"
ANNOTAISE_ENV_DIR="$envdir" bash "$here/write-env.sh" annotaise-test \
  https://lab.example.org/annotaise-test 8471 \
  --mail-user sender@example.org --mail-from "PrivDev <sender@example.org>" >/dev/null
envf="$envdir/.env"
check ".env exists" test -f "$envf"
check ".env mode is 0600" test "$(stat -c %a "$envf")" = 600
check "EMAIL_HOST_PASSWORD is empty" grep -qx 'EMAIL_HOST_PASSWORD=' "$envf"
check "operator comment about the password" grep -qi 'set .*EMAIL_HOST_PASSWORD' "$envf"
check "EMAIL_HOST" grep -qx 'EMAIL_HOST=smtp.gmail.com' "$envf"
check "EMAIL_PORT" grep -qx 'EMAIL_PORT=587' "$envf"
check "EMAIL_USE_TLS" grep -qx 'EMAIL_USE_TLS=True' "$envf"
check "EMAIL_HOST_USER" grep -qx 'EMAIL_HOST_USER=sender@example.org' "$envf"
check "DEFAULT_FROM_EMAIL" grep -qx 'DEFAULT_FROM_EMAIL=PrivDev <sender@example.org>' "$envf"
check "URL values derived" grep -qx 'DJANGO_FORCE_SCRIPT_NAME=/annotaise-test/backend' "$envf"
check "secrets generated, non-empty" bash -c "grep -Eq '^DJANGO_SECRET_KEY=.{30,}' '$envf' && grep -Eq '^DJANGO_DB_PASS=.{16,}' '$envf'"
before="$(grep '^DJANGO_DB_PASS=' "$envf")"
ANNOTAISE_ENV_DIR="$envdir" bash "$here/write-env.sh" annotaise-test \
  https://lab.example.org/annotaise-test 8471 >/dev/null
check "rerun keeps existing secrets" test "$(grep '^DJANGO_DB_PASS=' "$envf")" = "$before"
check "rerun keeps mail settings" grep -qx 'EMAIL_HOST_USER=sender@example.org' "$envf"
check "study hides admin" bash -c "ANNOTAISE_ENV_DIR='$work/s' bash '$here/write-env.sh' annotaise-study https://lab.example.org/annotaise 8472 >/dev/null && grep -qx GATEWAY_HIDE_ADMIN=1 '$work/s/.env'"

sed -i 's/^EMAIL_HOST_PASSWORD=.*/EMAIL_HOST_PASSWORD=hand-set-value/' "$envf"
ANNOTAISE_ENV_DIR="$envdir" bash "$here/write-env.sh" annotaise-test \
  https://lab.example.org/annotaise-test 8471 >/dev/null
check "rerun keeps a hand-set SMTP password" grep -qx 'EMAIL_HOST_PASSWORD=hand-set-value' "$envf"

# --- backup root is required (no silent default) ---
rc() { set +e; "$@" >/dev/null 2>&1; local s=$?; set -e; echo "$s"; }
check "backup.sh without ANNOTAISE_BACKUP_ROOT fails" \
  test "$(rc env -u ANNOTAISE_BACKUP_ROOT bash "$here/backup.sh" annotaise-test)" = 2
check "restore.sh without ANNOTAISE_BACKUP_ROOT fails" \
  test "$(rc env -u ANNOTAISE_BACKUP_ROOT bash "$here/restore.sh" annotaise-test /dev/null)" = 2
check "backup unit reads the root from an EnvironmentFile" \
  grep -qE '^EnvironmentFile=@[A-Z_]+@' "$here/systemd/annotaise-backup@.service"

# --- dataset timer units ---
svc="$here/systemd/privdev-dataset.service"
tim="$here/systemd/privdev-dataset.timer"
check "dataset service exists" test -f "$svc"
check "service runs the dataset CLI" grep -q 'uv run python -m privdev.annotation.dataset' "$svc"
check "service WorkingDirectory is a parameter" grep -qE '^WorkingDirectory=@[A-Z_]+@' "$svc"
check "WorkingDirectory is the privdev-mappings project" grep -qx 'WorkingDirectory=@PRIVDEV_MAPPINGS_DIR@' "$svc"
check "README installs into privdev-mappings" grep -q 's#@PRIVDEV_MAPPINGS_DIR@#.*/privdev-mappings#' "$here/README.md"
for var in LABELING_A LABELING_B ANNOTAISE_URL ANNOTAISE_EXPORT_EMAIL ANNOTAISE_EXPORT_PASSWORD; do
  check "service documents $var" grep -qE "^#.*\\b$var\\b" "$svc"
  check "README documents $var" grep -q "$var" "$here/README.md"
done
check "ANNOTAISE_URL documented as the backend base" grep -qE '^#.*ANNOTAISE_URL.*/backend' "$svc"
check "ExecStart runs through /bin/sh -c" grep -qE '^ExecStart=/bin/sh -c ' "$svc"
check "empty LABELING_B drops --labeling-b" grep -qF '${LABELING_B:+--labeling-b $LABELING_B}' "$svc"
check "no bare --labeling-b \${LABELING_B}" bash -c '! grep -qF -- "--labeling-b \${LABELING_B}" "$1"' _ "$svc"
check "service EnvironmentFile is a parameter" grep -qE '^EnvironmentFile=@[A-Z_]+@' "$svc"
check "timer fires nightly at 03:30 local" grep -qFx 'OnCalendar=*-*-* 03:30:00' "$tim"
check "service PATH includes ~/.local/bin (uv)" grep -q '^Environment=PATH=%h/.local/bin' "$svc"
check "timer is persistent" grep -qx 'Persistent=true' "$tim"

exit "$fail"
