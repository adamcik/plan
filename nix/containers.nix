{
  inputs,
  self,
  ...
}: {
  imports = [./modules/nix2container.nix];

  perSystem = {
    config,
    pkgs,
    inputs',
    ...
  }: let
    nix2containerPkgs = inputs'.nix2container.packages.nix2container;
    overrideMetadata = builtins.fromJSON (builtins.readFile inputs.build-overrides);
    fallbackCreated = let
      d = self.lastModifiedDate or "";
    in
      if d == "" || builtins.stringLength d < 14
      then "0001-01-01T00:00:00Z"
      else "${builtins.substring 0 4 d}-${builtins.substring 4 2 d}-${builtins.substring 6 2 d}T${builtins.substring 8 2 d}:${builtins.substring 10 2 d}:${builtins.substring 12 2 d}Z";
    uwsgiPkg = pkgs.uwsgi.override {
      python3 = config.uv2nix.python;
      plugins = ["python3"];
    };
    serveScript = pkgs.writeShellScriptBin "plan-uwsgi" ''
      set -eu

      export DJANGO_SETTINGS_MODULE="''${DJANGO_SETTINGS_MODULE:?DJANGO_SETTINGS_MODULE is required}"
      export PLAN_BASE_DIR="''${PLAN_BASE_DIR:?PLAN_BASE_DIR is required}"
      export PLAN_UWSGI_LISTENER="''${PLAN_UWSGI_LISTENER:?PLAN_UWSGI_LISTENER is required}"
      export PLAN_UWSGI_SOCKET="''${PLAN_UWSGI_SOCKET:?PLAN_UWSGI_SOCKET is required}"
      export PLAN_UWSGI_HTTP="''${PLAN_UWSGI_HTTP:?PLAN_UWSGI_HTTP is required}"
      export PLAN_UWSGI_PROCESSES="''${PLAN_UWSGI_PROCESSES:?PLAN_UWSGI_PROCESSES is required}"
      export PLAN_UWSGI_THREADS="''${PLAN_UWSGI_THREADS:?PLAN_UWSGI_THREADS is required}"
      export PLAN_UWSGI_LOG_FORMAT="''${PLAN_UWSGI_LOG_FORMAT:-off}"
      export PLAN_UWSGI_STATIC_URL="''${PLAN_UWSGI_STATIC_URL:-/_/static}"
      export PLAN_UWSGI_STATIC_ROOT="''${PLAN_UWSGI_STATIC_ROOT:-${staticAssets}/static}"

      uwsgi_args=(
        "--plugin" "python3"
        "--enable-threads"
        "--py-call-uwsgi-fork-hooks"
        "--log-5xx"
        "--log-master"
        "--static-map" "$PLAN_UWSGI_STATIC_URL=$PLAN_UWSGI_STATIC_ROOT"
        "--module" "plan.wsgi"
        "--virtualenv" "${config.uv2nix.runtimeVenv}"
        "--master"
        "--processes" "$PLAN_UWSGI_PROCESSES"
        "--threads" "$PLAN_UWSGI_THREADS"
        "--show-config"
        "--need-app"
      )

      if [ "$PLAN_UWSGI_LOG_FORMAT" = "off" ]; then
        uwsgi_args+=("--disable-logging")
      elif [ "$PLAN_UWSGI_LOG_FORMAT" = "on" ]; then
        uwsgi_args+=("--log-format" "%(addr) %(method) %(uri) => %(status) %(size)B %(msecs)ms")
      else
        uwsgi_args+=("--log-format" "$PLAN_UWSGI_LOG_FORMAT")
      fi

      case "$PLAN_UWSGI_LISTENER" in
        socket)
          uwsgi_args+=("--socket" "$PLAN_UWSGI_SOCKET" "--chmod-socket=660" "--vacuum")
          ;;
        http)
          uwsgi_args+=("--http" "$PLAN_UWSGI_HTTP")
          ;;
        both)
          uwsgi_args+=("--socket" "$PLAN_UWSGI_SOCKET" "--chmod-socket=660" "--vacuum" "--http" "$PLAN_UWSGI_HTTP")
          ;;
        *)
          echo "Unsupported PLAN_UWSGI_LISTENER: $PLAN_UWSGI_LISTENER" >&2
          exit 2
          ;;
      esac

      exec ${pkgs.lib.getExe uwsgiPkg} "''${uwsgi_args[@]}"
    '';
    manageScript = pkgs.writeShellScriptBin "manage" ''
      export DJANGO_SETTINGS_MODULE="''${DJANGO_SETTINGS_MODULE:?DJANGO_SETTINGS_MODULE is required}"
      export PLAN_BASE_DIR="''${PLAN_BASE_DIR:?PLAN_BASE_DIR is required}"

      exec ${pkgs.lib.getExe' config.uv2nix.manageVenv "python3"} -m django "$@"
    '';
    staticAssets =
      pkgs.runCommand "plan-static-assets" {
        nativeBuildInputs = [config.uv2nix.runtimeVenv];
        src = ../.;
      } ''
        mkdir -p "$TMPDIR/static"

        cd "$src"
        export DJANGO_SETTINGS_MODULE="plan.settings.container"
        export DJANGO_DEBUG_TOOLBAR=1
        export PLAN_BASE_DIR="$TMPDIR"
        export PLAN_STATIC_ROOT="$TMPDIR/static"
        export STATIC_URL="/_/static/"
        export DJANGO_SECRET_KEY="nix-build-static"
        python manage.py collectstatic --noinput
        python manage.py compress --force

        mkdir -p "$out/static"
        cp -r "$TMPDIR/static"/. "$out/static"
      '';

    # Keep fallback runtime paths writable for rootless runs without host mounts.
    # Most deployments bind-mount /var/lib/plan, /var/cache/plan, and /run/uwsgi
    # with tighter host-managed ownership/permissions, which override these modes.
    runtimeDirs = pkgs.runCommand "plan-runtime-dirs" {} ''
      for path in \
        "$out/run/uwsgi" \
        "$out/var/lib/plan" \
        "$out/var/cache/plan" \
        "$out/var/cache/plan/default" \
        "$out/var/cache/plan/ical" \
        "$out/var/cache/plan/scraper"
      do
        install -d -m 1777 "$path"
      done
      install -d -m 1777 "$out/tmp"
    '';

    staticLink = pkgs.runCommand "plan-static-link" {} ''
      install -d -m 0755 "$out/var/lib/plan"
      ln -s "${staticAssets}/static" "$out/var/lib/plan/static"
    '';
  in {
    nix2container = {
      name = "ghcr.io/adamcik/plan";
      tag = "latest";
      created =
        if ((overrideMetadata.created or null) != null)
        then overrideMetadata.created
        else fallbackCreated;

      imageConfig = {
        Cmd = [(pkgs.lib.getExe serveScript)];
        WorkingDir = "/app";
        User = "65532:65532";
        Env = [
          "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
          "PYTHONDONTWRITEBYTECODE=1"
          "DJANGO_SETTINGS_MODULE=plan.settings.container"
          "PLAN_BASE_DIR=/var/lib/plan"
          "PLAN_CACHE_DIR=/var/cache/plan"
          "PLAN_UWSGI_STATIC_ROOT=/var/lib/plan/static"
          "STATIC_URL=/_/static/"
          "PLAN_UWSGI_LISTENER=http"
          "PLAN_UWSGI_HTTP=0.0.0.0:8080"
          "PLAN_UWSGI_SOCKET=/run/uwsgi/uwsgi.sock"
          "PLAN_UWSGI_PROCESSES=4"
          "PLAN_UWSGI_THREADS=1"
        ];
        Labels = let
          created =
            if ((overrideMetadata.created or null) != null)
            then overrideMetadata.created
            else fallbackCreated;
        in
          {
            "org.opencontainers.image.created" = created;
            "org.opencontainers.image.description" = "Timetable generator for educational institutions.";
            "org.opencontainers.image.source" = "https://github.com/adamcik/plan";
            "org.opencontainers.image.title" = "plan";
          }
          // pkgs.lib.optionalAttrs ((overrideMetadata.revision or null) != null) {
            "org.opencontainers.image.revision" = overrideMetadata.revision;
          }
          // pkgs.lib.optionalAttrs ((overrideMetadata.version or null) != null) {
            "org.opencontainers.image.version" = overrideMetadata.version;
          };
      };

      layers = let
        baseLayer = nix2containerPkgs.buildLayer {
          deps = [
            uwsgiPkg
            config.uv2nix.python
          ];
        };
        depsLayer = nix2containerPkgs.buildLayer {
          deps = [config.uv2nix.depsVenv];
          layers = [baseLayer];
        };
        appLayer = nix2containerPkgs.buildLayer {
          deps = [
            config.uv2nix.runtimeVenv
            config.uv2nix.manageVenv
            staticAssets
          ];
          layers = [baseLayer depsLayer];
        };
        metadataLayer = nix2containerPkgs.buildLayer {
          copyToRoot = [
            (pkgs.buildEnv {
              name = "plan-root-bin";
              paths = [
                manageScript
                serveScript
              ];
              pathsToLink = ["/bin"];
            })
            staticLink
            runtimeDirs
          ];
          layers = [baseLayer depsLayer appLayer];
        };
      in [
        baseLayer
        depsLayer
        appLayer
        metadataLayer
      ];
    };
  };
}
