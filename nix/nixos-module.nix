{self}: {
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkOption types;
  cfg = config.services.plan;
  packages = self.packages.${pkgs.stdenv.hostPlatform.system};
  instances = lib.filterAttrs (_: instance: instance.enable) cfg.instances;
  unitNames = lib.concatLists (lib.mapAttrsToList (name: instance:
    ["plan-${name}" "plan-${name}-migrate" "plan-${name}-check"]
    ++ lib.optional (instance.refreshCalendar != null) "plan-${name}-refresh")
  instances);
  instanceType = types.submodule {
    options = {
      enable = lib.mkEnableOption "this Plan instance";
      port = mkOption {
        type = types.port;
        description = "Loopback HTTP port; each enabled instance needs a distinct port.";
      };
      environmentFile = mkOption {
        type = types.str;
        description = ''
          Absolute path to a systemd environment file containing runtime secrets,
          including DJANGO_SECRET_KEY. The file must exist before starting units;
          use a runtime path, not a Nix path literal that copies secrets to the store.
        '';
      };
      settings = mkOption {
        type = types.attrsOf types.str;
        default = {};
        description = ''
          Non-secret application environment settings. Values in environmentFile
          take precedence. Keep STATIC_URL=/_/static/ for the prebuilt assets;
          PLAN_* runtime paths and listener settings are managed by this module.
        '';
      };
      processes = mkOption {
        type = types.ints.positive;
        default = 4;
        description = "Number of uWSGI worker processes.";
      };
      threads = mkOption {
        type = types.ints.positive;
        default = 1;
        description = "Number of threads per uWSGI worker.";
      };
      refreshCalendar = mkOption {
        type = types.nullOr types.str;
        default = null;
        example = "*:0/30";
        description = ''
          Optional systemd calendar for refreshing materialized views. Enable on
          only one instance per database, including when prod and preprod share it.
        '';
      };
    };
  };
  environment = name: instance:
    instance.settings
    // {
      DJANGO_SETTINGS_MODULE = "plan.settings";
      PLAN_BASE_DIR = "/var/lib/plan-${name}";
      PLAN_CACHE_DIR = "/var/cache/plan-${name}";
      PLAN_STATIC_ROOT = cfg.staticRoot;
      STATIC_URL = "/_/static/";
      PLAN_UWSGI_STATIC_ROOT = cfg.staticRoot;
      PLAN_UWSGI_LISTENER = "http";
      PLAN_UWSGI_HTTP = "127.0.0.1:${toString instance.port}";
      PLAN_UWSGI_SOCKET = "/run/plan-${name}/uwsgi.sock";
      PLAN_UWSGI_PROCESSES = toString instance.processes;
      PLAN_UWSGI_THREADS = toString instance.threads;
      SSL_CERT_FILE = "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
      PYTHONDONTWRITEBYTECODE = "1";
    };
  serviceConfig = name: instance: {
    User = "plan-${name}";
    Group = "plan-${name}";
    EnvironmentFile = instance.environmentFile;
    WorkingDirectory = "/var/lib/plan-${name}";
    StateDirectory = "plan-${name}";
    CacheDirectory = "plan-${name}";
    StateDirectoryMode = "0750";
    CacheDirectoryMode = "0750";
    UMask = "0027";
    NoNewPrivileges = true;
    PrivateTmp = true;
    PrivateDevices = true;
    ProtectSystem = "strict";
    ProtectHome = true;
    ProtectKernelTunables = true;
    ProtectKernelModules = true;
    ProtectControlGroups = true;
    RestrictSUIDSGID = true;
    RestrictAddressFamilies = ["AF_UNIX" "AF_INET" "AF_INET6"];
    CapabilityBoundingSet = "";
  };
  commandUnit = name: instance: description: command: {
    inherit description;
    wants = ["network-online.target"];
    after = ["network-online.target"];
    environment = environment name instance;
    # Database writes require an explicit operator action, not a rebuild.
    restartIfChanged = false;
    serviceConfig =
      serviceConfig name instance
      // {
        Type = "oneshot";
        ExecStart = "${packages.plan-manage}/bin/manage ${command}";
      };
  };
in {
  options.services.plan = {
    instances = mkOption {
      type = types.attrsOf instanceType;
      default = {};
      description = "Independently configured Plan deployments with isolated users and directories.";
    };
    staticRoot = mkOption {
      type = types.str;
      readOnly = true;
      default = "${packages.plan-static}/static";
      description = "Matching immutable static assets to serve at /_/static/.";
    };
  };

  config = lib.mkIf (instances != {}) {
    assertions =
      [
        {
          assertion = let
            ports = map (instance: instance.port) (lib.attrValues instances);
          in
            lib.length ports == lib.length (lib.unique ports);
          message = "Enabled Plan instances must use distinct HTTP ports.";
        }
        {
          assertion = lib.length unitNames == lib.length (lib.unique unitNames);
          message = "Plan instance names must not collide with another instance's migrate, check, or refresh units.";
        }
      ]
      ++ lib.mapAttrsToList (name: instance: {
        assertion =
          builtins.match "[a-z][a-z0-9-]{0,25}" name
          != null
          && lib.hasPrefix "/" instance.environmentFile;
        message = "Plan instance names must match [a-z][a-z0-9-]{0,25} and environmentFile must be absolute.";
      })
      instances;

    users.users = lib.mapAttrs' (name: _:
      lib.nameValuePair "plan-${name}" {
        isSystemUser = true;
        group = "plan-${name}";
      })
    instances;
    users.groups = lib.mapAttrs' (name: _: lib.nameValuePair "plan-${name}" {}) instances;

    systemd.services = lib.mkMerge (lib.mapAttrsToList (name: instance:
      {
        "plan-${name}" = {
          description = "Plan web instance ${name}";
          wantedBy = ["multi-user.target"];
          wants = ["network-online.target"];
          after = ["network-online.target"];
          environment = environment name instance;
          serviceConfig =
            serviceConfig name instance
            // {
              ExecStart = "${packages.plan-web}/bin/plan-uwsgi";
              Restart = "on-failure";
              RestartSec = 5;
              TimeoutStopSec = 45;
            };
        };
        "plan-${name}-migrate" =
          commandUnit name instance
          "Apply Plan database migrations for ${name}" "migrate --noinput";
        "plan-${name}-check" =
          commandUnit name instance
          "Check Plan configuration and migrations for ${name}" "migrate --check";
      }
      // lib.optionalAttrs (instance.refreshCalendar != null) {
        "plan-${name}-refresh" =
          commandUnit name instance
          "Refresh Plan materialized views for ${name}" "refresh_materialized_views";
      })
    instances);

    systemd.timers = lib.mapAttrs' (name: instance:
      lib.nameValuePair "plan-${name}-refresh" {
        wantedBy = ["timers.target"];
        timerConfig = {
          OnCalendar = instance.refreshCalendar;
          Persistent = true;
          RandomizedDelaySec = "3m";
        };
      }) (lib.filterAttrs (_: instance: instance.refreshCalendar != null) instances);
  };
}
