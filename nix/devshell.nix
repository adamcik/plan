{...}: {
  perSystem = {
    config,
    lib,
    pkgs,
    ...
  }: let
    runDb = pkgs.writeShellScriptBin "run-db" ''
      set -euo pipefail

      REPO_ROOT=''${REPO_ROOT:-$(jj root 2>/dev/null || git rev-parse --show-toplevel)}
      PGDATA=''${PGDATA:-$REPO_ROOT/data/pgdata}
      PGHOST=''${PGHOST:-$PGDATA}
      PGDATABASE=''${PGDATABASE:-postgres}
      PGUSER=''${PGUSER:-$(whoami)}
      PGLOG=''${PGLOG:-$REPO_ROOT/data/postgres.log}

      mkdir -p "$PGDATA"

      if [ ! -f "$PGDATA/PG_VERSION" ]; then
        initdb -D "$PGDATA" >/dev/null
      fi

      exec postgres -D "$PGDATA" -k "$PGHOST" -h ""
    '';

    runContainer = pkgs.writeShellScriptBin "run-container" ''
      set -euo pipefail

      ENGINE="docker"
      IMAGE_REF="ghcr.io/adamcik/plan:latest"
      EXTRA_ARGS=()

      while [ "$#" -gt 0 ]; do
        case "$1" in
          --podman)
            ENGINE="podman"
            shift
            ;;
          --docker)
            ENGINE="docker"
            shift
            ;;
          --image)
            IMAGE_REF="$2"
            shift 2
            ;;
          --)
            shift
            EXTRA_ARGS=("$@")
            break
            ;;
          *)
            echo "Unknown argument: $1" >&2
            echo "Usage: run-container [--docker|--podman] [--image <ref>] [-- <extra container args>]" >&2
            exit 2
            ;;
        esac
      done

      REPO_ROOT=''${REPO_ROOT:-$(jj root 2>/dev/null || git rev-parse --show-toplevel)}
      PGHOST_DIR=''${PGHOST:-$REPO_ROOT/data/pgdata}
      CONTAINER_PGDATABASE=''${CONTAINER_PGDATABASE:-postgres}
      CONTAINER_PGUSER=''${CONTAINER_PGUSER:-$(whoami)}
      CONTAINER_PGPASSWORD=''${CONTAINER_PGPASSWORD:-}
      CONTAINER_PGPORT=''${CONTAINER_PGPORT:-5432}
      LOG_FORMAT=''${LOG_FORMAT:-on}

      if [ ! -S "$PGHOST_DIR/.s.PGSQL.$CONTAINER_PGPORT" ]; then
        echo "Postgres socket not found at $PGHOST_DIR/.s.PGSQL.$CONTAINER_PGPORT" >&2
        echo "Start DB first: run-db" >&2
        exit 1
      fi

      mkdir -p "$REPO_ROOT/data"

      if [ "$ENGINE" = "docker" ]; then
        nix run .#packages.x86_64-linux.image.copyToDockerDaemon
      else
        nix run .#packages.x86_64-linux.image.copyToPodman
      fi

      mkdir -p "$REPO_ROOT/data/cache/default" "$REPO_ROOT/data/cache/ical" "$REPO_ROOT/data/cache/scraper"

      echo "run-container: ENGINE=$ENGINE IMAGE_REF=$IMAGE_REF"
      echo "run-container: DJANGO_SETTINGS_MODULE=plan.settings.container PGDATABASE=$CONTAINER_PGDATABASE PGUSER=$CONTAINER_PGUSER PGHOST=/pgsocket PGPORT=$CONTAINER_PGPORT"

      exec "$ENGINE" run --rm --network host \
        --user "$(id -u):$(id -g)" \
        -e DJANGO_SETTINGS_MODULE=plan.settings.container \
        -e DJANGO_SECRET_KEY=dev \
        -e DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost \
        -e PGDATABASE="$CONTAINER_PGDATABASE" \
        -e PGUSER="$CONTAINER_PGUSER" \
        -e PGPASSWORD="$CONTAINER_PGPASSWORD" \
        -e PGHOST=/pgsocket \
        -e PGPORT="$CONTAINER_PGPORT" \
        -e PLAN_UWSGI_LOG_FORMAT="$LOG_FORMAT" \
        -v "$PGHOST_DIR:/pgsocket" \
        -v "$REPO_ROOT/data/cache:/var/cache/plan" \
        "''${EXTRA_ARGS[@]}" \
        "$IMAGE_REF"
    '';
  in {
    devShells.default = pkgs.mkShell {
      packages = with pkgs; [
        uv
        ruff
        basedpyright
        tombi
        djlint
        config.uv2nix.devVenv
        postgresql
        runDb
        runContainer
      ];
      env = {
        "DJANGO_SETTINGS_MODULE" = "plan.settings.default";
        "VIRTUAL_ENV" = "${config.uv2nix.devVenv}";
      };

      shellHook = ''
        unset PYTHONPATH
        export REPO_ROOT=$(jj root 2> /dev/null || git rev-parse --show-toplevel)
        export PATH="${config.uv2nix.devVenv}/bin:$PATH"
      '';

      # motd = ''
      #   {202}Plan development environment{reset}
      #   All dependencies are pre-installed via Nix (uv2nix).
      #   You do not need to run 'uv sync' in this shell.
      #
      #   PGHOST is dynamically set to your working directory (see shellHook).
      #
      #
      #    {bold}Available commands:{reset}
      #      ./manage.py runserver
      #      ruff check .                - Lint Python code
      #      basedpyright                - Type check Python code
      #
      #    {bold}To run tests:{reset}
      #      nix develop --command "./manage.py test"
      #
      #    Tests automatically run against an ephemeral PostgreSQL instance.
      # '';
    };

    devShells.playwright = pkgs.mkShell {
      packages = with pkgs; [
        nodejs
        playwright-driver
        playwright-mcp
      ];

      env = {
        PLAYWRIGHT_BROWSERS_PATH = "${pkgs.playwright-driver.browsers}";
        PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS = "true";

        OPENCODE_CONFIG_CONTENT = builtins.toJSON {
          mcp = {
            playwright-mcp = {
              type = "local";
              command = ["mcp-server-playwright"];
              enabled = true;
            };
          };
        };
      };
    };
  };
}
