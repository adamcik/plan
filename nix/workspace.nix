{inputs, ...}: {
  imports = [./modules/uv2nix.nix];
  perSystem = {
    config,
    lib,
    pkgs,
    ...
  }: let
    basePython = pkgs.python312;
    shrinkPython = false;
    python =
      if shrinkPython
      then
        basePython.override {
          bluezSupport = false;
          stripConfig = true;
          stripIdlelib = true;
          stripTests = true;
          stripTkinter = true;

          rebuildBytecode = false;
          stripBytecode = true;

          readline = null;
          ncurses = null;
          gdbm = null;
        }
      else basePython;
    editableVenv = config.uv2nix.devVenv;
    overrideMetadata = builtins.fromJSON (builtins.readFile inputs.build-overrides);
    hacks = pkgs.callPackage inputs.pyproject-nix.build.hacks {};
  in {
    uv2nix = {
      inherit python;
      pyprojectOverrides = final: prev: {
        brotli = hacks.nixpkgsPrebuilt {
          from = pkgs.python312Packages.brotli;
          prev = prev.brotli;
        };
        lxml = hacks.nixpkgsPrebuilt {
          from = pkgs.python312Packages.lxml;
          prev = prev.lxml;
        };
        pillow = hacks.nixpkgsPrebuilt {
          from = pkgs.python312Packages.pillow;
          prev = prev.pillow;
        };
        pylibmc = hacks.nixpkgsPrebuilt {
          from = pkgs.python312Packages.pylibmc;
          prev = prev.pylibmc;
        };
        psycopg2 = hacks.nixpkgsPrebuilt {
          from = pkgs.python312Packages.psycopg2;
          prev = prev.psycopg2;
        };
        reportlab = hacks.nixpkgsPrebuilt {
          from = pkgs.python312Packages.reportlab;
          prev = prev.reportlab;
        };
        plan = prev.plan.overrideAttrs (old: {
          env =
            (old.env or {})
            // lib.optionalAttrs ((overrideMetadata.version or null) != null) {
              SETUPTOOLS_SCM_PRETEND_VERSION = overrideMetadata.version;
            };
        });
      };
      workspaceRoot = toString (
        lib.fileset.toSource {
          root = ../.;
          fileset = lib.fileset.unions [
            ../pyproject.toml
            ../uv.lock
            ../plan
            ../README.md
          ];
        }
      );
    };

    checks = {
      django-check =
        pkgs.runCommand "django-check" {
          nativeBuildInputs = [editableVenv];
          src = ../.;
        } ''
          cd $src
          export DJANGO_SETTINGS_MODULE="plan.settings"
          export DJANGO_SECRET_KEY="test"
          export DJANGO_COMPRESS_ENABLED="false"
          export PLAN_BASE_DIR="$TMPDIR/plan"
          export PLAN_CACHE_DIR="$TMPDIR/cache"
          export PGHOST="$TMPDIR/pgsocket"
          mkdir -p "$PLAN_BASE_DIR"
          python manage.py check
          touch $out
        '';

      django-test =
        pkgs.runCommand "django-test" {
          nativeBuildInputs = [editableVenv pkgs.postgresql_16];
          src = ../.;
        } ''
           cd $src
          export DJANGO_SETTINGS_MODULE="plan.settings"
          export DJANGO_SECRET_KEY="test"
          export DJANGO_COMPRESS_ENABLED="false"
          export PLAN_BASE_DIR="$TMPDIR/plan"
          export PLAN_CACHE_DIR="$TMPDIR/cache"
          export PGHOST="$TMPDIR/pgsocket"
          mkdir -p "$PLAN_BASE_DIR"
          python manage.py test --noinput
          touch $out
        '';

      django-static-assets =
        pkgs.runCommand "django-static-assets" {
          nativeBuildInputs = [editableVenv];
          src = ../.;
        } ''
          cd $src
          export DJANGO_SETTINGS_MODULE="plan.settings"
          export DJANGO_SECRET_KEY="test"
          export DJANGO_COMPRESS_ENABLED="false"
          export PLAN_BASE_DIR="$TMPDIR/plan"
          export PLAN_CACHE_DIR="$TMPDIR/cache"
          export PLAN_STATIC_ROOT="$TMPDIR/static"
          export DJANGO_COMPRESS_ENABLED="true"
          mkdir -p "$PLAN_BASE_DIR" "$PLAN_CACHE_DIR" "$PLAN_STATIC_ROOT"
          python manage.py collectstatic --noinput
          python manage.py compress --force
          touch $out
        '';

      django-i18n =
        pkgs.runCommand "django-i18n" {
          nativeBuildInputs = [
            editableVenv
            pkgs.gettext
            pkgs.findutils
            pkgs.coreutils
            pkgs.diffutils
          ];
          src = ../.;
        } ''
          set -euo pipefail

          cp -r --no-preserve=mode,ownership "$src" "$TMPDIR/before"
          cp -r --no-preserve=mode,ownership "$src" "$TMPDIR/after"
          chmod -R u+w "$TMPDIR/after"

          po_manifest() {
            find "$1" -name '*.po' -type f -print0 \
              | sort -z \
              | xargs -0 sha256sum \
              | sed "s#$1/##"
          }

          po_manifest "$TMPDIR/before" > "$TMPDIR/before.po.sha256"

          cd "$TMPDIR/after"
          export DJANGO_SETTINGS_MODULE="plan.settings"
          export DJANGO_SECRET_KEY="test"
          export PLAN_BASE_DIR="$TMPDIR/plan"
          export PLAN_CACHE_DIR="$TMPDIR/cache"
          export PGHOST="$TMPDIR/pgsocket"
          mkdir -p "$PLAN_BASE_DIR"

          python manage.py compilemessages
          python manage.py makemessages --all --no-location

          cd "$TMPDIR"
          po_manifest "$TMPDIR/after" > "$TMPDIR/after.po.sha256"

          if ! diff -u "$TMPDIR/before.po.sha256" "$TMPDIR/after.po.sha256"; then
            echo "Translation files are out of date. Run: python manage.py makemessages --all --no-location"
            exit 1
          fi

          touch $out
        '';

      django-i18n-untranslated =
        pkgs.runCommand "django-i18n-untranslated" {
          nativeBuildInputs = [pkgs.gettext pkgs.findutils pkgs.gnugrep];
          src = ../.;
        } ''
          set -euo pipefail

          cd "$src"

          flag_file="$TMPDIR/i18n-untranslated-found"
          find . -name '*.po' -type f | while IFS= read -r po; do
            untranslated="$TMPDIR/untranslated-$(basename "$po")"
            msgattrib --untranslated --no-obsolete --no-fuzzy "$po" > "$untranslated"

            if grep -q '^msgid "' "$untranslated"; then
              echo "Untranslated strings found in $po"
              touch "$flag_file"
            fi
          done

          if [ -f "$flag_file" ]; then
            echo "Untranslated translation entries detected."
            exit 1
          fi

          touch $out
        '';
    };
  };
}
