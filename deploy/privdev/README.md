# PrivDev Study 1 deployment (AgentBox)

Two independent AnnotAISE instances run on AgentBox from this fork (branch
`privdev/study1`), each as its own Docker Compose project with its own
containers, network, volumes and `.env`:

| Instance | Visibility | URL | Loopback port |
|---|---|---|---|
| `annotaise-test` | **Tailnet-only** | https://agentbox.tail289ef2.ts.net:9446/annotaise-test/ | `127.0.0.1:8471` |
| `annotaise-study` | **Public** (Tailscale Funnel) | https://agentbox.tail289ef2.ts.net:8443/annotaise/ | `127.0.0.1:8472` |

The study instance is the one annotators use; it was made public with the
project lead's authorisation (design §3, 2026-11-17). The test instance is for
dry runs and restore checks and stays Tailnet-only.

## How it fits together

```
browser ── Tailscale Serve/Funnel ── /<mount>/ (prefix stripped) ── 127.0.0.1:<port>
                                                                    └─ gateway (nginx, in the project)
                                                                         /backend/static/* → Django static (volume)
                                                                         /backend/*        → api:8000 (gunicorn), prefix stripped
                                                                         /*                → frontend:3000 (Next.js, basePath re-added)
```

* Both Tailscale listeners already have their URL root taken by other services,
  so each instance lives beneath a path mount. Tailscale strips the mount prefix
  before proxying; the gateway is the single loopback port per instance.
* Next.js is built with `basePath = NEXT_PUBLIC_BASE_PATH` (`/annotaise-test` or
  `/annotaise`). The frontend is built when its container starts (upstream
  `run.sh`), so `NEXT_PUBLIC_*` values take effect on the next restart; a start
  takes a few minutes (npm install + `next build`).
* The API is at `<URL>/backend/` (e.g. `<URL>/backend/api/schema/`,
  `<URL>/backend/admin/`), because several API routes (`/labelings/...`) have the
  same names as frontend pages. Django gets its public prefix from
  `DJANGO_FORCE_SCRIPT_NAME` (`<mount>/backend`).
* Overrides in `compose.override.yaml`: no source bind mounts (the code baked
  into the images runs), `DEBUG=0` (gunicorn + collectstatic), all ports bound to
  `127.0.0.1` (only the gateway publishes one; the database publishes none),
  `restart: unless-stopped`, and the frontend no longer reads the repository
  root `.env` (that one belongs to the local dev stack `annotaise`).
* Fork changes that make the sub-path work (all env-driven; defaults keep the
  upstream behaviour): `backend/annotaise/settings.py` (`DEBUG` parsing,
  `DJANGO_FORCE_SCRIPT_NAME`, extra CSRF/CORS origins, `DJANGO_COOKIE_DOMAIN`),
  `backend/run.sh` (`DEBUG=0` selects gunicorn), `frontend/next.config.ts`
  (`basePath`), `frontend/src/lib/basePath.ts` and its use for public-asset logos
  and the forced-logout redirect.

## Port map

| Port | Bound to | What |
|---|---|---|
| 8471 | 127.0.0.1 | `annotaise-test` gateway → Tailnet 9446 `/annotaise-test/` |
| 8472 | 127.0.0.1 | `annotaise-study` gateway → Funnel 8443 `/annotaise/` |
| 55432 | 0.0.0.0 | *not ours*: the local dev database `annotaise-db-1` (project `annotaise`) |

Containers: `annotaise-test-{db,api,frontend,gateway}-1` and
`annotaise-study-{db,api,frontend,gateway}-1`. Volumes:
`<project>_pg_annotaise`, `<project>_static_volume_annotaise`,
`<project>_media_annotaise`.

## Secrets and `.env`

Secrets are only in the AgentBox secret store
`/etc/agentbox/secrets/annotaise/{test,study}/` (root-only, mode 0700/0600) and
in each instance's `deploy/privdev/<project>/.env` (mode 0600, git-ignored by the
repository's `.env` rule; check with `git check-ignore -v`). Each instance has its
own values for `annotaise-django-secret`, `annotaise-db-password`,
`annotaise-superuser-password` and `annotaise-export-password`.

(Re)write an instance's `.env` from the store, giving its public URL and port:

```sh
sudo deploy/privdev/write-env.sh annotaise-test  https://agentbox.tail289ef2.ts.net:9446/annotaise-test 8471
sudo deploy/privdev/write-env.sh annotaise-study https://agentbox.tail289ef2.ts.net:8443/annotaise      8472
```

It derives `FRONTEND_URL`, `NEXT_PUBLIC_BASE_PATH`, `NEXT_PUBLIC_API_BASE_URL`,
`DJANGO_FORCE_SCRIPT_NAME`, allowed hosts and CSRF origins from the URL and never
prints a secret. The Django superuser is `admin@annotaise.invalid` (log in by
email) with the instance's `annotaise-superuser-password`. To rotate a secret,
replace its file in the store with a new CSPRNG value, rerun `write-env.sh` and
restart the instance (the database password also has to be changed inside
Postgres, since the image only applies it on first initialisation).

## Start, stop, status

Run from the repository root; `P` is `annotaise-test` or `annotaise-study`.

```sh
P=annotaise-study
dc() { docker compose -p "$P" -f docker-compose.yaml -f deploy/privdev/compose.override.yaml \
         --env-file "deploy/privdev/$P/.env" "$@"; }

dc up -d --build     # start, or apply code/config changes
dc ps                # status
dc logs -f frontend  # wait for "Ready in" after a (re)start
dc restart           # restart (frontend rebuilds)
dc stop              # stop, keeping data
```

Never use `dc down -v`: it deletes the instance's database volume.

If the frontend log loops on `Bus error (core dumped)` during `next build`, its
`npm install` left a truncated native binary (seen once after a slow download).
Recreate the container to get a fresh install: `dc up -d --force-recreate --no-deps frontend`.

## Backups

`backup.sh <project>` runs `pg_dump -Fc` inside the instance's db container and
writes `/srv/projects/annotaise/runtime/backups/<project>/<UTC timestamp>.dump`
(directory mode 0700; dumps contain personal data). It keeps the newest dump of
each of the 14 most recent days and of each of the 8 most recent ISO weeks.

Nightly systemd user timers (02:30 UTC, `Persistent=true`; user lingering is
enabled for `simon`) run it for both instances. Units live in `systemd/`:

```sh
install -m 0644 deploy/privdev/systemd/annotaise-backup@.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now annotaise-backup@annotaise-test.timer annotaise-backup@annotaise-study.timer
systemctl --user list-timers 'annotaise-backup@*'
journalctl --user -u 'annotaise-backup@*'          # results
systemctl --user start annotaise-backup@annotaise-study.service   # ad-hoc backup
```

## Restore

```sh
deploy/privdev/restore.sh <project> /srv/projects/annotaise/runtime/backups/<project>/<stamp>.dump
```

Destructive: it stops the project, removes its Postgres volume, recreates an
empty database, loads the dump with `pg_restore --exit-on-error --no-owner`
and starts the project again. Take a fresh `backup.sh` first if the current
data matter.

Restore check (done on `annotaise-test` on 2026-11-17 before launch): a labeling
with 3 submitted answers was exported (`/backend/labelings/<id>/answers/export/`)
to `before.csv`, backed up, the volume removed and restored, and exported again
to `after.csv`; `cmp before.csv after.csv` exited 0, and the answers were still
there after restarting both stacks.

## Publishing and unpublishing

Published with the AgentBox runbook (`/srv/agent-platform/docs/runbooks/expose.md`):

```sh
agentctl expose http://127.0.0.1:8471 --mount annotaise-test            # Tailnet-only
agentctl expose http://127.0.0.1:8472 --mount annotaise --public        # Public
```

To remove a publication, use the mount and the port from its URL (this removes
only that mount; other routes are untouched):

```sh
agentctl unexpose annotaise-test --port 9446
agentctl unexpose annotaise --port 8443
```

Never run `tailscale serve reset` / `tailscale funnel reset`. If a listener
port ever changes, rerun `write-env.sh` with the new URL and restart the
instance, since the URL is baked into the frontend build.
