# Podman + systemd Deployment (Debian 11 / Podman 3)

This deployment flow is for hosts without Quadlet support.

- Debian 11 (bullseye)
- Podman 3.x
- systemd units generated with `podman generate systemd --new`
- Socket-based app traffic (no published HTTP port)

Scraper jobs are intentionally out of scope here.

## Files in this directory

- `plan.env.example`
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
- `PLAN_BASE_DIR=/var/lib/plan`
- `PLAN_UWSGI_LISTENER=socket`
- `PLAN_UWSGI_SOCKET=/run/uwsgi/uwsgi.sock`

Note: `/var/lib/plan` stores writable app state:

- `static/CACHE`
- `cache/default`
- `cache/ical`
- `cache/scraper`

## 2) Pull image + create pod + container

Use a pod even with one app container so additional sidecars can be added later.

```bash
sudo podman pod rm -f plan || true
sudo podman rm -f plan-ntnu || true

sudo podman pull ghcr.io/adamcik/plan:latest
sudo podman pod create --name plan

sudo podman create \
  --name plan-ntnu \
  --pod plan \
  --user 33:33 \
  --env DJANGO_SETTINGS_MODULE=plan.settings.container \
  --env-file /etc/plan/plan.env \
  -v /var/lib/plan:/var/lib/plan \
  -v /run/plan:/run/uwsgi \
  ghcr.io/adamcik/plan:latest
```

No `-p/--publish` is needed. Traffic is through unix socket only.

If old Podman bridge networking is flaky for outbound traffic, recreate pod with host networking:

```bash
sudo podman pod rm -f plan
sudo podman pod create --name plan --network host
```

## 3) Generate + install systemd units

```bash
sudo podman generate systemd --name plan --files --new

sudo install -D -m 0644 pod-plan.service /etc/systemd/system/pod-plan.service
sudo install -D -m 0644 container-plan-ntnu.service /etc/systemd/system/container-plan-ntnu.service
```

## 4) Add path ownership override

```bash
sudo mkdir -p /etc/systemd/system/container-plan-ntnu.service.d
sudo tee /etc/systemd/system/container-plan-ntnu.service.d/paths.conf >/dev/null <<'EOF'
[Service]
ExecStartPre=/usr/bin/install -d -o www-data -g www-data -m 0750 /var/lib/plan
ExecStartPre=/usr/bin/install -d -o root -g www-data -m 2775 /run/plan
EOF
```

`/run/plan` uses setgid (`2775`) so socket group ownership stays compatible with reverse proxy access.

## 5) Enable and start

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pod-plan.service container-plan-ntnu.service
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

## 7) Verify

```bash
sudo systemctl status pod-plan.service --no-pager
sudo systemctl status container-plan-ntnu.service --no-pager
sudo systemctl status plan-materialized-refresh.timer --no-pager

sudo podman ps --filter name=plan-ntnu
sudo ls -l /run/plan/uwsgi.sock

sudo podman logs --tail 100 plan-ntnu
sudo systemctl list-timers --all | grep plan-materialized-refresh
```

Run one manual refresh test:

```bash
sudo systemctl start plan-materialized-refresh.service
sudo systemctl status plan-materialized-refresh.service --no-pager
```

## 8) Reverse proxy (Caddy)

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
