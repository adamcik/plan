{...}: {
  imports = [./modules/nix2container.nix];

  perSystem = {
    config,
    pkgs,
    inputs',
    ...
  }: let
    nix2containerPkgs = inputs'.nix2container.packages.nix2container;
    uwsgiPkg = pkgs.uwsgi.override {
      python3 = config.uv2nix.python;
      plugins = ["python3"];
    };
    serveScript = pkgs.writeShellScriptBin "plan-uwsgi" ''
      set -eu

      listener="''${PLAN_UWSGI_LISTENER:-socket}"
      socket_path="''${PLAN_UWSGI_SOCKET:-/run/uwsgi/uwsgi.sock}"
      http_bind="''${PLAN_UWSGI_HTTP:-0.0.0.0:8080}"
      processes="''${PLAN_UWSGI_PROCESSES:-4}"
      threads="''${PLAN_UWSGI_THREADS:-4}"
      default_log_format="%(addr) - - [%(ltime)] \"%(var.REQUEST_METHOD) %(var.REQUEST_URI) %(var.SERVER_PROTOCOL)\" %(status) %(size) \"%(var.HTTP_REFERER)\" \"%(var.HTTP_USER_AGENT)\" host=\"%(var.HTTP_HOST)\" xfp=\"%(var.HTTP_X_FORWARDED_PROTO)\""
      log_format="''${PLAN_UWSGI_LOG_FORMAT-__DEFAULT__}"

      if [ "$log_format" = "__DEFAULT__" ]; then
        log_format="$default_log_format"
      fi

      uwsgi_args=(
        "--plugin" "python3"
        "--ignore-sigpipe"
        "--ignore-write-errors"
        "--disable-write-exception"
        "--env" "DJANGO_SETTINGS_MODULE=''${DJANGO_SETTINGS_MODULE:-plan.settings.container}"
        "--env" "PLAN_BASE_DIR=''${PLAN_BASE_DIR:-/var/lib/plan}"
        "--static-map" "/static/CACHE=/var/lib/plan/static/CACHE"
        "--static-map" "/static=${staticAssets}/static"
        "--module" "plan.wsgi"
        "--virtualenv" "${config.uv2nix.runtimeVenv}"
        "--master"
        "--processes" "$processes"
        "--threads" "$threads"
        "--show-config"
        "--need-app"
      )

      case "$log_format" in
        ""|off|OFF|disabled|DISABLED)
          ;;
        *)
          uwsgi_args+=("--log-format" "$log_format")
          ;;
      esac

      case "$listener" in
        socket)
          uwsgi_args+=("--socket" "$socket_path" "--chmod-socket=660" "--vacuum")
          ;;
        http)
          uwsgi_args+=("--http" "$http_bind")
          ;;
        both)
          uwsgi_args+=("--socket" "$socket_path" "--chmod-socket=660" "--vacuum" "--http" "$http_bind")
          ;;
        *)
          echo "Unsupported PLAN_UWSGI_LISTENER: $listener" >&2
          exit 2
          ;;
      esac

      exec ${pkgs.lib.getExe uwsgiPkg} "''${uwsgi_args[@]}"
    '';
    manageScript = pkgs.writeShellScriptBin "manage" ''
      export DJANGO_SETTINGS_MODULE="''${DJANGO_SETTINGS_MODULE:-plan.settings.container}"
      export PLAN_BASE_DIR="''${PLAN_BASE_DIR:-/var/lib/plan}"
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
        export PLAN_BASE_DIR="$TMPDIR"
        export DJANGO_SECRET_KEY="nix-build-static"
        python manage.py collectstatic --noinput

        mkdir -p "$out/static"
        cp -r "$TMPDIR/static"/. "$out/static"
      '';
  in {
    nix2container = {
      name = "ghcr.io/adamcik/plan";
      tag = "latest";

      imageConfig = {
        Cmd = [(pkgs.lib.getExe serveScript)];
        WorkingDir = "/app";
        User = "1234:1234";
        Env = ["SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"];
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
            (pkgs.buildEnv {
              name = "plan-root-bin";
              paths = [
                manageScript
                serveScript
              ];
              pathsToLink = ["/bin"];
            })
          ];
          layers = [baseLayer depsLayer];
        };
      in [
        baseLayer
        depsLayer
        appLayer
      ];
    };
  };
}
