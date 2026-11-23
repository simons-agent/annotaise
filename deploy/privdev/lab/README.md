# Lab production host (Proxmox LXC 112, `privdev.aise-lab.com`)

The production instance runs as `annotaise-study` in the AISE lab container
`annotaise-simon` (Ubuntu 26.04, sudo-rs). Differences from "Fresh host" in
`../README.md`:

* **Rootful Podman.** Rootless Podman cannot create user namespaces in this LXC
  (`cannot clone: Permission denied`), so compose runs as root through the
  Docker-compatible socket: `podman-docker` + `docker-compose-v2`,
  `COMPOSE="docker compose"`, `podman.socket` enabled.
* **URL root.** Cloudflare Tunnel (managed by the lab admins, `cloudflared`
  service) maps `https://privdev.aise-lab.com` to `http://localhost:8080`:
  `write-env.sh annotaise-study https://privdev.aise-lab.com 8080 ...`
  (empty base path, API at `/backend`).
* **Paths.** Checkout `/opt/annotaise/repo`, backups `/opt/annotaise/backups`
  (`/etc/annotaise/backup.env`), logs `/opt/annotaise/logs`.
* **System units** (files in this directory, installed to `/etc/systemd/system`):
  `annotaise-study.service` starts the stack at boot (Podman's
  `podman-restart.service` only restarts `restart: always` containers);
  `annotaise-backup@annotaise-study.timer` (from `../systemd`, with
  `WorkingDirectory=/opt/annotaise/repo` added) at 02:30 UTC;
  `annotaise-status.timer` runs `/usr/local/bin/annotaise-status` daily at
  09:00 America/Sao_Paulo (results: `journalctl -u annotaise-status`).
* **Updates.** `20auto-upgrades` goes to `/etc/apt/apt.conf.d/`
  (unattended security updates).
* **Access.** SSH via Cloudflare Access: `ssh-privdev.aise-lab.com`,
  `ProxyCommand cloudflared access ssh --hostname %h`; the Access token lasts
  24 h (`cloudflared access login https://ssh-privdev.aise-lab.com`).
* **Known build hiccup.** The first `next build` once failed resolving
  `next/font/google` (Google returned `/l/font?kit=` URLs); a plain retry worked.
