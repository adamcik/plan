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
{config, inputs, pkgs, ...}: {
  imports = [inputs.plan.nixosModules.default];

  services.plan.instances.ntnu = {
    enable = true;
    credentials = {
      DJANGO_SECRET_KEY = "/run/secrets/plan-ntnu-key";
      PGPASSWORD = "/run/secrets/plan-ntnu-db-password";
    };
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
      locations."/".extraConfig = ''
        include ${pkgs.nginx}/conf/uwsgi_params;
        uwsgi_pass unix:${config.services.plan.instances.ntnu.socketPath};
      '';
    };
  };
  users.users.nginx.extraGroups = [config.services.plan.instances.ntnu.socketGroup];
}
```

Each instance listens on `/run/plan-<name>/uwsgi.sock`, using the **uWSGI protocol,
not HTTP**. No application TCP port is opened. Add the proxy user to that instance's
`socketGroup` and restart the proxy after changing group membership. The socket is
mode `0660`; its dedicated proxy group does not grant access to private state or
cache directories. systemd recreates the runtime directory after reboot.
Configure forwarded HTTPS headers to match your proxy and Django settings before
exposing the instance publicly. The example deliberately does not configure TLS.

### Caddy alternative

For an existing Caddy setup, grant the same per-instance socket access:

```nix
users.users.caddy.extraGroups = [config.services.plan.instances.ntnu.socketGroup];
```

Use the module's `staticRoot` and instance `socketPath` in the virtual host:

```nix
services.caddy.virtualHosts."plan.example.org".extraConfig = ''
  handle_path /_/static/* {
    root * ${config.services.plan.staticRoot}
    file_server
  }
  handle {
    reverse_proxy unix/${config.services.plan.instances.ntnu.socketPath} {
      transport uwsgi
    }
  }
'';
```

The `uwsgi` transport requires a Caddy build with that plugin; stock Caddy does not
include it. This uses the same protocol as the existing container deployment.

### Instance isolation

The instance creates the `plan-ntnu` user and group, `/var/lib/plan-ntnu`, and
`/var/cache/plan-ntnu`. Both directories are private to that instance's user and
group. A hardened systemd unit runs the web process without container tooling.

## Secrets and environment

Put non-secret configuration in `settings`. Use your host's secret manager to
provision root-readable files (for example, mode `0600`) before starting units.
Each credential file contains only its secret value, not `NAME=value` syntax.
The supported credential names are `DJANGO_SECRET_KEY`, `PGPASSWORD`, and
`SENTRY_DSN`. Omit `PGPASSWORD` when using PostgreSQL peer authentication.

The module uses systemd `LoadCredential=` for the web, migration, check, and refresh
units. systemd gives each unit private credential files and sets
`CREDENTIALS_DIRECTORY`. Plan points Pydantic's native secrets source at that
directory; credential names match the existing settings aliases. No `*_FILE`
variables or launcher exports are needed. Secret values are not exported into the
process environment. The instance user need not read the original source files.
An explicit Pydantic `_secrets_dir` or configured `secrets_dir` takes precedence
over automatic systemd discovery, so tests and other deployment environments can
select a different directory.

Do not put secrets in `settings` or use Nix path literals for credential sources:
that copies secrets into the Nix store. Supply absolute runtime path strings, as
in the example. Arrange ordering on your secret-management unit if necessary.
Missing configured credential sources fail systemd startup. Pydantic strips leading
and trailing whitespace from secret files and reports read/decoding errors during
settings initialization. It retains ordinary source precedence: explicit constructor
values, environment, dotenv, secret files, then defaults. Do not set a secret in the
environment if you intend its credential file to be authoritative. Credential files
must contain non-empty values suitable for the corresponding setting.

Restart the web unit after rotating credentials. Management units load current
credentials on each invocation. `LoadCredential=` handles delivery to processes,
not provisioning, encryption at rest, or automatic rotation.

### Environment-file compatibility

An optional `environmentFile = "/run/secrets/plan-ntnu.env"` retains the existing
environment-based configuration. Values in that file override `settings` and
credential files, following Pydantic's standard precedence. Prefer credentials for
new native deployments; never export credential contents through a launcher.

Do not copy the container environment file unchanged: omit `PLAN_BASE_DIR`,
`PLAN_CACHE_DIR`, `PLAN_STATIC_ROOT`, `PLAN_UWSGI_*`, `DJANGO_SETTINGS_MODULE`, and
`STATIC_URL`. The module manages these for the native deployment. Precompressed
assets require `STATIC_URL=/_/static/`. Other settings are documented in `env.example`.

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
It verifies explicit migrations, database-backed requests through Unix sockets,
socket permissions, absence of application TCP listeners, private state/cache
directories (including isolation from the proxy), refresh-job opt-in, restart
persistence, credential delivery without secret environment values, legacy
environment-file compatibility, and proxy-served static assets while the application is stopped.
The VM test needs a Linux builder with KVM.
No production infrastructure or external application endpoints are involved.
