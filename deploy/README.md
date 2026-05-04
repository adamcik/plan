# Podman + systemd Deployment (Debian 11 / Podman 3)

This deployment flow is for hosts without Quadlet support.

- Debian 11 (bullseye)
- Podman 3.x
- systemd units generated with `podman generate systemd --new`
- Socket-based app traffic (no published HTTP port)
- Host networking on the app container (`--network host`)

Scraper jobs are intentionally out of scope here.

## Files in this directory

- `plan.env.example`
- `plan-collectstatic.service`
- `plan-materialized-refresh.service`
- `plan-materialized-refresh.timer`

## 1) Prepare host paths + env

```bash
sudo install -d -m 0750 /etc/plan
sudo install -d -o www-data -g www-data -m 0750 /var/lib/plan
sudo install -d -o root -g www-data -m 2775 /run/plan

sudo cp deploy/plan.env.example /etc/plan/plan.env

sudo editor /etc/plan/plan.env
```

Required in `/etc/plan/plan.env`:

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGHOST`, `PGPORT`, `PGCONN_MAX_AGE`
- `PLAN_UWSGI_LISTENER=socket`
- `PLAN_UWSGI_SOCKET=/run/uwsgi/uwsgi.sock`

Image defaults already provide `DJANGO_SETTINGS_MODULE=plan.settings.container` and
`PLAN_BASE_DIR=/var/lib/plan`. This deploy flow still sets socket listener vars in
`/etc/plan/plan.env` to override image default HTTP mode.

Note: `/var/lib/plan` stores writable app state:

- `static/CACHE`
- `cache/default`
- `cache/ical`
- `cache/scraper`

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
  --env-file /etc/plan/plan.env \
  --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,noexec,size=256m,mode=1777 \
  -v /var/lib/plan:/var/lib/plan \
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

## 7) Install collectstatic service (manual on-demand)

```bash
sudo install -D -m 0644 deploy/plan-collectstatic.service /etc/systemd/system/plan-collectstatic.service

sudo systemctl daemon-reload
sudo systemctl enable plan-collectstatic.service
```

Run when needed (for example after deploying a new image version):

```bash
sudo systemctl start plan-collectstatic.service
sudo systemctl status plan-collectstatic.service --no-pager
```

## 8) Enable and start services

```bash
sudo systemctl enable --now container-plan-ntnu.service
```

## 9) Verify

```bash
sudo systemctl status container-plan-ntnu.service --no-pager
sudo systemctl status plan-collectstatic.service --no-pager
sudo systemctl status plan-materialized-refresh.timer --no-pager

sudo podman ps --filter name=plan-ntnu
sudo ls -l /run/plan/uwsgi.sock

sudo podman logs --tail 100 plan-ntnu
sudo systemctl list-timers --all | grep plan-materialized-refresh
```

Run manual maintenance tests:

```bash
sudo systemctl start plan-collectstatic.service
sudo systemctl status plan-collectstatic.service --no-pager

sudo systemctl start plan-materialized-refresh.service
sudo systemctl status plan-materialized-refresh.service --no-pager
```

## 10) Reverse proxy (Caddy)

Use the socket path `/run/plan/uwsgi.sock`.

```caddy
rewrite /timeplan /timeplan/
reverse_proxy /timeplan/* unix//run/plan/uwsgi.sock {
  transport uwsgi
}
```

Then apply:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

## Optional: Podman-managed named volume instead of host bind

If you prefer internal Podman state over `/var/lib/plan` bind mount:

```bash
sudo podman volume create plan-state
```

Then use:

- `-v plan-state:/var/lib/plan`

Host bind mount is still recommended when you want straightforward backups and host-level inspection.

## Notes

- Static assets are collected at image build time already. Runtime writes are mainly cache/compressor output under `/var/lib/plan`.
- `DJANGO_SETTINGS_MODULE` is pinned to `plan.settings.container` in container args to reduce accidental drift.
