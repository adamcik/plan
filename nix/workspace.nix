{...}: {
  imports = [./modules/uv2nix.nix];
  perSystem = {
    config,
    inputs',
    lib,
    pkgs,
    ...
  }: let
    pkgsLegacy = inputs'.nixpkgs-legacy.legacyPackages;
    shrinkPython = false;
    python =
      if shrinkPython
      then
        pkgsLegacy.python310.override {
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
      else pkgsLegacy.python310;
    editableVenv = config.uv2nix.devVenv;
  in {
    uv2nix = {
      inherit python;
      pyprojectOverrides = final: prev: let
        inherit (final) resolveBuildSystem;
        overrides = with pkgsLegacy; {
          rjsmin.buildInputs = resolveBuildSystem {setuptools = [];};
          rcssmin.buildInputs = resolveBuildSystem {setuptools = [];};
          vobject.buildInputs = resolveBuildSystem {setuptools = [];};
          psycopg2.buildInputs = resolveBuildSystem {setuptools = [];} ++ [libpq.pg_config];
          brotli = {
            buildInputs =
              resolveBuildSystem {
                setuptools = [];
                pkgconfig = [];
              }
              ++ [brotli];
            nativeBuildInputs = [pkg-config];
            env.USE_SYSTEM_BROTLI = 1;
          };
          reportlab = {
            buildInputs = resolveBuildSystem {setuptools = [];} ++ [freetype libjpeg zlib];
            nativeBuildInputs = [pkg-config];
            compile_flags = [
              "-std=gnu89"
              "-Wno-error=deprecated-declarations"
              "-Wno-error=incompatible-pointer-types"
            ];
          };
          pillow = {
            buildInputs =
              resolveBuildSystem {
                setuptools = [];
                pybind11 = [];
              }
              # TODO: add back libavif libtiff libxcb
              ++ [freetype lcms2 libimagequant libjpeg libraqm openjpeg zlib-ng libwebp];
            nativeBuildInputs = [pkg-config];
          };
          lxml = {
            buildInputs =
              resolveBuildSystem {
                cython = [];
                setuptools = [];
              }
              ++ [libxml2 libxslt zlib];
            compile_flags = [
              "-Wno-error=incompatible-pointer-types"
              "-Wno-error=deprecated-declarations"
              "-Wno-error=int-conversion"
              "-fpermissive"
            ];
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
          python manage.py test --noinput
          touch $out
        '';
    };
  };
}
