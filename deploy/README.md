# Podman + Quadlet Deployment (Debian trixie)

Canonical setup in this repo is:

- root-managed Quadlet units in `/etc/containers/systemd/`
- one instance per unit/container (`plan-<instance>`)
- instance-scoped host paths (`/var/lib/plan/<instance>`, `/var/cache/plan/<instance>`, `/run/plan/<instance>`)
- Caddy proxies to per-instance unix socket (`/run/plan/<instance>/uwsgi.sock`)

This doc intentionally describes only that model.

## Files in this directory

- `env.example`
- `plan-instance.container.example`
- `migrate.sh`
- `upgrade.sh` (optional convenience)
- `plan-materialized-refresh.service`
- `plan-materialized-refresh.timer`

## 1) Choose instance

Examples in this doc use `ntnu`. Replace with `prod`/`preprod` as needed.

## 2) Prepare host dirs + env

```bash
sudo install -d -m 0750 /etc/plan
sudo install -m 0640 deploy/env.example /etc/plan/ntnu.env
sudo editor /etc/plan/ntnu.env

sudo install -d -o www-data -g www-data -m 0750 /var/lib/plan/ntnu
sudo install -d -o www-data -g www-data -m 0750 /var/cache/plan/ntnu
```

Required in `/etc/plan/ntnu.env`:

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGHOST`, `PGPORT`, `PGCONN_MAX_AGE`
- `PLAN_UWSGI_LISTENER=socket`
- `PLAN_UWSGI_SOCKET=/run/uwsgi/uwsgi.sock`
- `STATIC_URL`

## 3) Install Quadlet file

Copy `deploy/plan-instance.container.example` to `/etc/containers/systemd/plan-ntnu.container`
and replace `<instance>` with your instance name. Result should look like:

```ini
[Unit]
Description=Plan app container (plan-ntnu)
Wants=network-online.target
After=network-online.target

[Container]
ContainerName=plan-ntnu
Image=ghcr.io/adamcik/plan:latest
Network=host
EnvironmentFile=/etc/plan/ntnu.env
User=33
Group=33
ReadOnly=true
Tmpfs=/tmp:rw,nosuid,nodev,noexec,size=256m,mode=1777
DropCapability=all
Volume=/var/lib/plan/ntnu:/var/lib/plan:rw,nosuid,nodev,noexec
Volume=/var/cache/plan/ntnu:/var/cache/plan:rw,nosuid,nodev,noexec
Volume=/run/plan/ntnu:/run/uwsgi:rw,nosuid,nodev,noexec

[Service]
Restart=always
RestartSec=5
TimeoutStopSec=45
NoNewPrivileges=yes
ExecStartPre=/usr/bin/install -d -o root -g www-data -m 2775 /run/plan/ntnu

[Install]
WantedBy=multi-user.target
```

Notes:

- Use `NoNewPrivileges=yes` in `[Service]` (not `SecurityOpt=`), for compatibility with Podman 5.4 Quadlet parsing.
- Add `ExecStartPre=/usr/bin/install -d ... /run/plan/<instance>` so reboot-cleared `/run` is recreated before each start.
- If you run as another uid/gid (for example dedicated `plan-prod:www-data`), set `User=`/`Group=` accordingly.

## 4) Reload + start

```bash
sudo systemctl daemon-reload
sudo systemctl enable /etc/containers/systemd/plan-ntnu.container
sudo systemctl start plan-ntnu.service
```

## 5) Verify

```bash
sudo systemctl status plan-ntnu.service --no-pager
sudo podman ps --filter name=plan-ntnu
sudo ls -l /run/plan/ntnu/uwsgi.sock
sudo podman logs --tail 100 plan-ntnu
```

## 6) Caddy wiring

Use:

- app socket: `/run/plan/ntnu/uwsgi.sock`
- static root: `/var/lib/plan/ntnu/static/current` (`/_/static/*`)

```caddy
rewrite /timeplan /timeplan/
handle_path /_/static/* {
  root * /var/lib/plan/ntnu/static/current
  file_server
}
reverse_proxy /timeplan/* unix//run/plan/ntnu/uwsgi.sock {
  transport uwsgi
}
```

Apply:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

## Migrations

```bash
deploy/migrate.sh --instance ntnu --image ghcr.io/adamcik/plan:<tag>
deploy/migrate.sh --instance ntnu --apply --image ghcr.io/adamcik/plan:<tag>
```

`deploy/migrate.sh` default behavior is `showmigrations --plan` + `migrate --check`.
`--apply` is explicit and does not imply `--check` unless `--check` is also passed.

## Upgrades (optional helper)

`deploy/upgrade.sh` is optional convenience; manual Quadlet flow is valid.

Default helper flow:

1. Pull image
2. Optionally extract static from image to `/var/lib/plan/<instance>/static/releases/<image-id>`
3. Atomically flip `/var/lib/plan/<instance>/static/current`
4. Write Quadlet image override drop-in:
   - `/etc/containers/systemd/plan-<instance>.container.d/image.conf`
5. `daemon-reload` + restart `plan-<instance>.service`

Example:

```bash
deploy/upgrade.sh --instance ntnu --check
deploy/upgrade.sh --instance ntnu --image ghcr.io/adamcik/plan:<tag>
```

Manual equivalent (without helper):

1. `sudo podman pull <image>`
2. Update `/etc/containers/systemd/plan-<instance>.container.d/image.conf`
3. If needed, handle static extraction/symlink flip
4. `sudo systemctl daemon-reload && sudo systemctl restart plan-<instance>.service`

## Shared refresh timer (current behavior)

`plan-materialized-refresh.service` currently targets `plan-ntnu` and is shared.
This is acceptable while prod/preprod use the same DB.
