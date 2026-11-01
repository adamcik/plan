# Native NixOS deployment

Import this flake's `nixosModules.default`. The module runs the same web launcher,
management environment, and immutable static assets as the container. It currently
supports `x86_64-linux`, matching the flake's package outputs.

The module does not provision PostgreSQL, memcached, TLS, DNS, or backups. Configure
those separately with their NixOS modules or connect to existing infrastructure.
The container deployment remains supported during migration.

## Configure an instance

For a host flake with this repository available as the `plan` input:

```nix
{config, inputs, ...}: {
  imports = [inputs.plan.nixosModules.default];

  services.plan.instances.ntnu = {
    enable = true;
    port = 8081;
    environmentFile = "/run/secrets/plan-ntnu.env";
    settings = {
      DJANGO_ALLOWED_HOSTS = "plan.example.org";
      DJANGO_CSRF_TRUSTED_ORIGINS = "https://plan.example.org";
      PGHOST = "127.0.0.1";
      PGDATABASE = "plan";
      PGUSER = "plan";
    };
    # Enable on only one instance per database.
    refreshCalendar = "*:0/30";
  };

  services.nginx = {
    enable = true;
    virtualHosts."plan.example.org" = {
      # Configure TLS here using your host's existing certificate policy.
      locations."/_/static/".alias = "${config.services.plan.staticRoot}/";
      locations."/".proxyPass = "http://127.0.0.1:8081";
    };
  };
}
```

Every enabled instance needs a distinct loopback HTTP port. The proxy uses ordinary
HTTP; no uWSGI proxy plugin or access to application-owned directories is needed.
Configure forwarded HTTPS headers to match your proxy and Django settings before
exposing the instance publicly. The example deliberately does not configure TLS.

The instance creates the `plan-ntnu` user and group, `/var/lib/plan-ntnu`, and
`/var/cache/plan-ntnu`. Both directories are private to that instance's user and
group. A hardened systemd unit runs the web process without container tooling.

## Secrets and environment

Use your host's secret manager to create a root-readable systemd environment file
before starting the instance, for example with mode `0600`:

```dotenv
DJANGO_SECRET_KEY=replace-with-a-secret
PGPASSWORD=replace-with-the-database-password
```

Do not put secrets in `settings` or use a Nix path literal for `environmentFile`;
that would expose them through the Nix store. The secret file is loaded by systemd,
so the application user does not need permission to read it. Arrange ordering on
your secret-management unit if necessary. Missing files cause startup to fail.

Values in the file override `settings`. Do not copy the container environment file
unchanged: omit `PLAN_BASE_DIR`, `PLAN_CACHE_DIR`, `PLAN_STATIC_ROOT`,
`PLAN_UWSGI_*`, `DJANGO_SETTINGS_MODULE`, and `STATIC_URL`. The module manages these
for the native deployment. Precompressed assets require `STATIC_URL=/_/static/`.
Other application settings are documented in `env.example`.

## Database operations

Web startup and `nixos-rebuild switch` **do not run migrations**. The module exposes
manual oneshot units:

```sh
sudo systemctl start plan-ntnu-check.service
sudo systemctl start plan-ntnu-migrate.service
sudo systemctl restart plan-ntnu.service
sudo journalctl -u plan-ntnu-migrate.service
```

The check runs `migrate --check`, failing when migrations are pending; it does not
change the database. The migration unit runs `migrate --noinput` as the instance
user with the same settings and secret file as the web unit. It is never enabled
at boot or automatically restarted when configuration changes. Applying migrations
is an operator decision: review them and back up the database first. Stop web
traffic before applying migrations that are incompatible with the running code.

If PostgreSQL is local, add ordering on `postgresql.service` to the web and database
operation units. Provision roles, databases, and authentication separately. The
module also supports remote databases and therefore does not assume a local unit.

When `refreshCalendar` is set, `plan-ntnu-refresh.timer` invokes
`plan-ntnu-refresh.service`. This runs `refresh_materialized_views` independently
of the web unit. Do not configure multiple refresh timers against a shared database.

## Migration and rollback

1. Keep the existing container available while preparing the native host.
2. Provision secrets, database access, backups, and any required state transfer.
3. Review and explicitly apply pending migrations with the oneshot unit.
4. Verify database-backed pages and static assets behind the new proxy before
   switching traffic. The proxy must serve the static output from the same flake
   revision as the application.
5. Retain the previous deployment until the new host is verified.

The module does not import container volumes or run the old upgrade/static-copy
scripts. Nix retains store outputs referenced by system generations, so separate
static-release extraction and garbage collection are unnecessary. NixOS rollback
restores code and configuration, **not database schemas or data**. Database
compatibility and recovery need their own plan.

## Verification

```sh
nix fmt
nix flake check
nix build .#image --no-link
```

`checks.x86_64-linux.nixos-service` boots a VM with PostgreSQL and two instances.
It verifies explicit migrations, database-backed HTTP requests, private state/cache
directories, refresh-job opt-in, restart persistence, and proxy-served static assets
while the application is stopped. The VM test needs a Linux builder with KVM.
No production infrastructure or external application endpoints are involved.
