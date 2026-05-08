# Podman + systemd Deployment (Debian 11 / Podman 3)

This deployment flow is for hosts without Quadlet support.

- Debian 11 (bullseye)
- Podman 3.x
- systemd units generated with `podman generate systemd --new`
- Socket-based app traffic (no published HTTP port)
- Host networking on the app container (`--network host`)

Scraper jobs are intentionally out of scope here.

## Files in this directory

- `env.example`
- `migrate.sh`
- `plan-materialized-refresh.service`
- `plan-materialized-refresh.timer`

## 1) Prepare host paths + env

```bash
sudo install -d -m 0750 /etc/plan
sudo install -d -o www-data -g www-data -m 0750 /var/lib/plan
sudo install -d -o www-data -g www-data -m 0750 /var/cache/plan
sudo install -d -o root -g www-data -m 2775 /run/plan

sudo install -m 0640 deploy/env.example /etc/plan/env

sudo editor /etc/plan/env
```

Required in `/etc/plan/env`:

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGHOST`, `PGPORT`, `PGCONN_MAX_AGE`
- `PLAN_UWSGI_LISTENER=socket`
- `PLAN_UWSGI_SOCKET=/run/uwsgi/uwsgi.sock`
- `STATIC_URL=/_/static/` (or absolute URL)
- `COMPRESS_URL=/_/cache/` (or absolute URL)

Recommended root split for container runtime:

- `PLAN_STATIC_ROOT=/static` (immutable assets in image)
- `PLAN_CACHE_DIR=/var/cache/plan` (writable cache root)
- `PLAN_COMPRESS_ROOT=/var/cache/plan/static` (writable compressor output)

Image defaults already provide `DJANGO_SETTINGS_MODULE=plan.settings.container` and
`PLAN_BASE_DIR=/var/lib/plan`. This deploy flow still sets socket listener vars in
`/etc/plan/env` to override image default HTTP mode.

Note:

- `/var/lib/plan` stores static release artifacts managed by deploy tooling.
- `/var/cache/plan` stores writable runtime cache state.

- `default`
- `ical`
- `scraper`
- `static` (compressor output for `/_/cache/*`)

Static files for Caddy are best served from a host-managed immutable release path,
not from `/var/lib/plan/static`.

## 2) Pull image + create container

If migrating from a running pod-based setup, remove pod + old container first:

```bash
sudo systemctl stop container-plan-ntnu.service pod-plan.service || true
sudo systemctl disable pod-plan.service || true
sudo podman rm -f plan-ntnu || true
sudo podman pod rm -f plan || true
```

```bash
sudo podman pull ghcr.io/adamcik/plan:latest

sudo podman create \
  --name plan-ntnu \
  --network host \
  --user 33:33 \
  --env-file /etc/plan/env \
  --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,noexec,size=256m,mode=1777 \
  -v /var/lib/plan:/var/lib/plan \
  -v /var/cache/plan:/var/cache/plan \
  -v /run/plan:/run/uwsgi \
  ghcr.io/adamcik/plan:latest
```

No `-p/--publish` is needed. Traffic is through unix socket only.

## 3) Generate + install systemd units

```bash
sudo podman generate systemd --name plan-ntnu --files --new

sudo install -D -m 0644 container-plan-ntnu.service /etc/systemd/system/container-plan-ntnu.service
sudo rm -f /etc/systemd/system/pod-plan.service
```

## 4) Add service drop-ins (paths + stop behavior)

```bash
sudo mkdir -p /etc/systemd/system/container-plan-ntnu.service.d
sudo tee /etc/systemd/system/container-plan-ntnu.service.d/paths.conf >/dev/null <<'EOF'
[Service]

ExecStartPre=/usr/bin/install -d -o www-data -g www-data -m 0750 /var/lib/plan
ExecStartPre=/usr/bin/install -d -o www-data -g www-data -m 0750 /var/lib/plan/static
ExecStartPre=/usr/bin/install -d -o www-data -g www-data -m 0750 /var/lib/plan/static/releases
ExecStartPre=/usr/bin/install -d -o www-data -g www-data -m 0750 /var/cache/plan
ExecStartPre=/usr/bin/install -d -o www-data -g www-data -m 0750 /var/cache/plan/static

ExecStartPre=/usr/bin/install -d -o root -g www-data -m 2775 /run/plan
EOF

sudo tee /etc/systemd/system/container-plan-ntnu.service.d/stop.conf >/dev/null <<'EOF'
[Service]

ExecStop=
ExecStop=/usr/bin/podman kill --signal QUIT --cidfile /run/container-plan-ntnu.ctr-id
ExecStop=-/usr/bin/podman wait --cidfile /run/container-plan-ntnu.ctr-id

TimeoutStopSec=45
EOF
```

`/run/plan` uses setgid (`2775`) so socket group ownership stays compatible with reverse proxy access.
`stop.conf` avoids TERM-timeout restarts on older Podman by using QUIT + wait.

## 5) Reload systemd

```bash
sudo systemctl daemon-reload
```

## 6) Install materialized-view refresh timer

```bash
sudo install -D -m 0644 deploy/plan-materialized-refresh.service /etc/systemd/system/plan-materialized-refresh.service
sudo install -D -m 0644 deploy/plan-materialized-refresh.timer /etc/systemd/system/plan-materialized-refresh.timer

sudo systemctl daemon-reload
sudo systemctl enable --now plan-materialized-refresh.timer
```

This timer runs:

```bash
podman exec plan-ntnu /bin/manage refresh_materialized_views
```

## 7) Enable and start services

```bash
sudo systemctl enable --now container-plan-ntnu.service
```

## 8) Verify

```bash
sudo systemctl status container-plan-ntnu.service --no-pager
sudo systemctl status plan-materialized-refresh.timer --no-pager

sudo podman ps --filter name=plan-ntnu
sudo ls -l /run/plan/uwsgi.sock

sudo podman logs --tail 100 plan-ntnu
sudo systemctl list-timers --all | grep plan-materialized-refresh
```

Run manual maintenance tests:

```bash
sudo systemctl start plan-materialized-refresh.service
sudo systemctl status plan-materialized-refresh.service --no-pager
```

## 9) Reverse proxy (Caddy)

Use:

- app socket path `/run/plan/uwsgi.sock`
- static root symlink `/var/lib/plan/static/current` for `/_/static/*`
- cache root `/var/cache/plan/static` for `/_/cache/*`

```bash
sudo install -d -o www-data -g www-data -m 0750 /var/lib/plan/static/releases
sudo install -d -o www-data -g www-data -m 0750 /var/lib/plan/static
sudo install -d -o www-data -g www-data -m 0750 /var/cache/plan/static
```

```caddy
rewrite /timeplan /timeplan/
handle_path /_/static/* {
  root * /var/lib/plan/static/current
  file_server
}
handle_path /_/cache/* {
  root * /var/cache/plan/static
  file_server
}
reverse_proxy /timeplan/* unix//run/plan/uwsgi.sock {
  transport uwsgi
}
```

Then apply:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

## Optional: Podman-managed named volumes instead of host binds

If you prefer internal Podman state over host bind mounts:

```bash
sudo podman volume create plan-state-lib
sudo podman volume create plan-state-cache
```

Then use:

- `-v plan-state-lib:/var/lib/plan`
- `-v plan-state-cache:/var/cache/plan`

Host bind mount is still recommended when you want straightforward backups and host-level inspection.

## Notes

- Static assets are collected at image build time. `deploy/upgrade.sh` can extract `/static` from the pulled image into `/var/lib/plan/static/releases/<image-id>` and atomically switch `/var/lib/plan/static/current`.
- Keep symlink switching on the host (outside the container) for atomicity and least privilege.
- Runtime writes are mainly cache/compressor output under `/var/cache/plan`.
- `DJANGO_SETTINGS_MODULE` defaults to `plan.settings.container` in the image to reduce accidental drift.

## Migrations

Run schema migrations as an explicit pre-flip step:

```bash
deploy/migrate.sh --show-plan
deploy/migrate.sh --image ghcr.io/adamcik/plan:<tag>
```

Default behavior uses `/etc/plan/env` and mounts `/var/lib/plan` + `/var/cache/plan`.

## Recommended release order

```bash
deploy/upgrade.sh --check
deploy/migrate.sh --image ghcr.io/adamcik/plan:<tag>
deploy/upgrade.sh --image ghcr.io/adamcik/plan:<tag>
```

By default, `deploy/upgrade.sh` now:

1. Pulls image
2. Extracts static from image to host release dir
3. Atomically flips `/var/lib/plan/static/current`
4. Restarts/recreates the app container

Optional flags:

- `--no-extract-static` to skip static extraction
- `--static-from`, `--static-releases`, `--static-current` to override paths
