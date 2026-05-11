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
    uvLock = inputs.uv2nix.lib.lock1.parseLock (lib.importTOML ../uv.lock);

    normalizeVersion = version: builtins.head (lib.splitString "+" version);
    packageFromLock = name: lib.findFirst (pkg: pkg.name == name) null uvLock.package;
    lockVersion = name: let
      pkg = packageFromLock name;
    in
      if pkg == null
      then null
      else normalizeVersion pkg.version;

    heavyDeps = {
      brotli = pkgs.python312Packages.brotli.version;
      lxml = pkgs.python312Packages.lxml.version;
      pillow = pkgs.python312Packages.pillow.version;
      psycopg2 = pkgs.python312Packages.psycopg2.version;
      reportlab = pkgs.python312Packages.reportlab.version;
    };

    heavyDepMismatches = lib.filter (line: line != null) (
      lib.mapAttrsToList (
        name: nixVersion: let
          normalizedNixVersion = normalizeVersion nixVersion;
          uvVersion = lockVersion name;
        in
          if uvVersion == null
          then "missing in uv.lock: ${name}"
          else if uvVersion != normalizedNixVersion
          then "version mismatch for ${name}: uv.lock=${uvVersion} nixpkgs=${normalizedNixVersion}"
          else null
      )
      heavyDeps
    );
  in {
    uv2nix = {
      inherit python;
      pyprojectOverrides = final: prev: let
        inherit (final) resolveBuildSystem;
        overrides = with pkgs; {
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
      deps = pkgs.runCommand "deps" {} ''
        if [ ${toString (builtins.length heavyDepMismatches)} -ne 0 ]; then
          echo "Native-heavy dependency version mismatch detected between uv.lock and nixpkgs:"
          ${lib.concatMapStringsSep "\n" (line: "echo \"  - ${line}\"") heavyDepMismatches}
          exit 1
        fi

        touch $out
      '';

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
