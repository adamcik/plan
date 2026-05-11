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
  in {
    uv2nix = {
      inherit python;
      pyprojectOverrides = final: prev: let
        inherit (final) resolveBuildSystem;
        overrides = with pkgs; {
          psycopg2.buildInputs = resolveBuildSystem {setuptools = [];} ++ [libpq.pg_config];
          plan.env = lib.optionalAttrs ((overrideMetadata.version or null) != null) {
            SETUPTOOLS_SCM_PRETEND_VERSION = overrideMetadata.version;
          };
        };
      in
        builtins.mapAttrs (
          name: {
            buildInputs ? [],
            nativeBuildInputs ? [],
            compile_flags ? [],
            env ? {},
          }:
            prev.${name}.overrideAttrs (old: {
              buildInputs = (old.buildInputs or []) ++ buildInputs;
              nativeBuildInputs = (old.nativeBuildInputs or []) ++ nativeBuildInputs;
              env = env // {NIX_CFLAGS_COMPILE = builtins.concatStringsSep " " compile_flags;};
            })
        )
        overrides;
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
          export DJANGO_SETTINGS_MODULE="plan.settings.test"
          python manage.py check
          touch $out
        '';

      django-test =
        pkgs.runCommand "django-test" {
          nativeBuildInputs = [editableVenv pkgs.postgresql_16];
          src = ../.;
        } ''
          cd $src
          export DJANGO_SETTINGS_MODULE="plan.settings.test"
          export DJANGO_SECRET_KEY="test"
          export PLAN_BASE_DIR="$TMPDIR/plan"
          python manage.py test --noinput
          touch $out
        '';
    };
  };
}
