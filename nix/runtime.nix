{...}: {
  perSystem = {
    config,
    lib,
    pkgs,
    ...
  }: let
    projectPkgs = import ./packages.nix {inherit pkgs;};
    staticAssets =
      pkgs.runCommand "plan-static-assets" {
        nativeBuildInputs = [config.uv2nix.runtimeVenv];
        src = ../.;
      } ''
        mkdir -p "$TMPDIR/static"
        cd "$src"
        export DJANGO_SETTINGS_MODULE="plan.settings"
        export DJANGO_DEBUG_TOOLBAR=1
        export PLAN_BASE_DIR="$TMPDIR"
        export PLAN_STATIC_ROOT="$TMPDIR/static"
        export STATIC_URL="/_/static/"
        export DJANGO_SECRET_KEY="nix-build-static"
        export DJANGO_COMPRESS_ENABLED="true"
        python manage.py collectstatic --noinput
        python manage.py compress --force

        mkdir -p "$out/static"
        cp -r "$TMPDIR/static"/. "$out/static"
      '';
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
        "--lazy-apps"
        "--py-call-uwsgi-fork-hooks"
        "--log-5xx"
        "--log-master"
        "--static-map" "$PLAN_UWSGI_STATIC_URL=$PLAN_UWSGI_STATIC_ROOT"
        # The minimal image has no /etc/mime.types; keep this database in its closure.
        "--mime-file" "${pkgs.mailcap}/etc/mime.types"
        "--module" "plan.wsgi"
        "--virtualenv" "${config.uv2nix.runtimeVenv}"
        "--master"
        "--die-on-term"
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

      if [ -n "''${PLAN_UWSGI_SOCKET_OWNER:-}" ]; then
        uwsgi_args+=("--chown-socket" "$PLAN_UWSGI_SOCKET_OWNER")
      fi

      exec ${lib.getExe projectPkgs.uwsgi} "''${uwsgi_args[@]}"
    '';
    manageScript = pkgs.writeShellScriptBin "manage" ''
      set -eu
      export DJANGO_SETTINGS_MODULE="''${DJANGO_SETTINGS_MODULE:?DJANGO_SETTINGS_MODULE is required}"
      export PLAN_BASE_DIR="''${PLAN_BASE_DIR:?PLAN_BASE_DIR is required}"

      exec ${lib.getExe' config.uv2nix.manageVenv "python3"} -m django "$@"
    '';
  in {
    packages = {
      plan-web = serveScript;
      plan-manage = manageScript;
      plan-static = staticAssets;
    };

    checks.runtime-packages =
      pkgs.runCommand "plan-runtime-packages" {
        nativeBuildInputs = [pkgs.shellcheck];
      } ''
        shellcheck ${serveScript}/bin/plan-uwsgi ${manageScript}/bin/manage

        export DJANGO_SETTINGS_MODULE=plan.settings
        export DJANGO_SECRET_KEY=runtime-package-check
        export PLAN_BASE_DIR="$TMPDIR/state"
        export PLAN_CACHE_DIR="$TMPDIR/cache"
        export PLAN_STATIC_ROOT=${staticAssets}/static
        export STATIC_URL=/_/static/
        mkdir -p "$PLAN_BASE_DIR" "$PLAN_CACHE_DIR"
        ${manageScript}/bin/manage check
        test -s "$PLAN_STATIC_ROOT/CACHE/manifest.json"

        export PLAN_UWSGI_LISTENER=invalid
        export PLAN_UWSGI_SOCKET="$TMPDIR/uwsgi.sock"
        export PLAN_UWSGI_HTTP=127.0.0.1:8080
        export PLAN_UWSGI_PROCESSES=1
        export PLAN_UWSGI_THREADS=1
        status=0
        ${serveScript}/bin/plan-uwsgi > "$TMPDIR/listener-error" 2>&1 || status=$?
        test "$status" -eq 2
        grep -F 'Unsupported PLAN_UWSGI_LISTENER: invalid' "$TMPDIR/listener-error"
        touch "$out"
      '';
  };
}
