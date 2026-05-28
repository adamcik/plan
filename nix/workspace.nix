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
          export DJANGO_SETTINGS_MODULE="plan.settings.default"
          export DJANGO_SECRET_KEY="test"
          export PLAN_BASE_DIR="$TMPDIR/plan"
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
          export DJANGO_SETTINGS_MODULE="plan.settings.default"
          export DJANGO_SECRET_KEY="test"
          export PLAN_BASE_DIR="$TMPDIR/plan"
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
          export DJANGO_SETTINGS_MODULE="plan.settings.default"
          export DJANGO_SECRET_KEY="test"
          export PLAN_BASE_DIR="$TMPDIR/plan"
          export PLAN_CACHE_DIR="$TMPDIR/cache"
          export PLAN_STATIC_ROOT="$TMPDIR/static"
          mkdir -p "$PLAN_BASE_DIR" "$PLAN_CACHE_DIR" "$PLAN_STATIC_ROOT"
          python manage.py collectstatic --noinput
          python manage.py compress --force
          touch $out
        '';
    };
  };
}
