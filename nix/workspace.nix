{inputs, ...}: {
  imports = [./modules/uv2nix.nix];

  perSystem = {
    config,
    lib,
    pkgs,
    ...
  }: let
    python = pkgs.python312.override {
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
      withSqlite = false;
    };

    editableVenv = config.uv2nix.devVenv;
    overrideMetadata = builtins.fromJSON (builtins.readFile inputs.build-overrides);
  in {
    uv2nix = {
      inherit python;
      pyprojectOverrides = final: prev: let
        inherit (final) resolveBuildSystem;
      in {
        django = prev.django.overrideAttrs (old: {
          postInstall = builtins.concatStringsSep "\n" [
            (old.postInstall or "")
            ''
              set -eu

              # This app only needs staticfiles/contenttypes from django.contrib.
              CONTRIB="$out/${final.python.sitePackages}/django/contrib"
              if [ -d "$CONTRIB" ]; then
                KEEP="staticfiles|contenttypes|__init__.py"
                ls -1 "$CONTRIB" | grep -vE "^($KEEP)$" | xargs -r -I {} rm -rf "$CONTRIB/{}"
              fi

              # Keep only locales supported by the application.
              find $out -name "locale" -type d -exec sh -c '
                set -eu
                cd "$1"
                for d in */; do
                  lang="''${d%/}"
                  case "$lang" in
                    en|no|nb|nn) ;;
                    *) rm -rf "$lang" ;;
                  esac
                done
              ' -- {} \;
            ''
          ];
        });

        # These are somewhat heavy, ideally we would use prebuilt nixpkgs, but
        # since we shrink our python we need to build them to ensure ABI
        # matches.

        brotli = prev.brotli.overrideAttrs (old: {
          buildInputs =
            (old.buildInputs or [])
            ++ (resolveBuildSystem {
              setuptools = [];
              pkgconfig = [];
            })
            ++ [pkgs.brotli];
          nativeBuildInputs =
            (old.nativeBuildInputs or [])
            ++ [pkgs.pkg-config pkgs.coreutils];
          env = (old.env or {}) // {USE_SYSTEM_BROTLI = 1;};
        });

        lxml = prev.lxml.overrideAttrs (old: {
          buildInputs =
            (old.buildInputs or [])
            ++ (resolveBuildSystem {
              cython = [];
              setuptools = [];
            })
            ++ [pkgs.libxml2 pkgs.libxslt pkgs.zlib];
          nativeBuildInputs =
            (old.nativeBuildInputs or [])
            ++ [pkgs.coreutils pkgs.findutils];
        });

        pillow = prev.pillow.overrideAttrs (old: {
          buildInputs =
            (old.buildInputs or [])
            ++ (resolveBuildSystem {
              setuptools = [];
              pybind11 = [];
            })
            ++ [
              pkgs.libjpeg
              pkgs.zlib
              pkgs.libwebp
            ];
          nativeBuildInputs =
            (old.nativeBuildInputs or [])
            ++ [pkgs.pkg-config pkgs.coreutils];
        });

        psycopg2 = prev.psycopg2.overrideAttrs (old: {
          buildInputs =
            (old.buildInputs or [])
            ++ (resolveBuildSystem {setuptools = [];})
            ++ [pkgs.libpq.pg_config];
        });

        pylibmc = prev.pylibmc.overrideAttrs (old: {
          buildInputs =
            (old.buildInputs or [])
            ++ (resolveBuildSystem {setuptools = [];})
            ++ [
              pkgs.libmemcached
              pkgs.zlib
            ];
        });

        reportlab = prev.reportlab.overrideAttrs (old: {
          buildInputs =
            (old.buildInputs or [])
            ++ (resolveBuildSystem {setuptools = [];})
            ++ [
              pkgs.freetype
              pkgs.libjpeg
              pkgs.zlib
            ];
          nativeBuildInputs =
            (old.nativeBuildInputs or [])
            ++ [pkgs.pkg-config pkgs.coreutils];
        });

        # Inject SETUPTOOLS_SCM_PRETEND_VERSION since we don't have access to
        # VCS info in nix builds.
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
          nativeBuildInputs = [editableVenv pkgs.postgresql_17];
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
