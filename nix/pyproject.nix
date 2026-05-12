{pkgs}:
# Shared uv2nix package overrides for third-party Python dependencies.
#
# This file centralizes build/shrink overrides for heavy C-extension packages
# (and Django pruning) so workspace.nix can stay focused on wiring.
#
# We intentionally do not use `hacks.nixpkgsPrebuilt` here. The runtime Python
# is a custom slim derivation, so prebuilt nixpkgs Python packages frequently
# end up with a different interpreter derivation and trigger ABI mismatch
# warnings/errors for extension modules.
#
# For the same reason, we avoid wheels for these packages and build from sdist
# (configured in uv2nix module with `no-binary-package`). Building locally keeps
# extensions linked against the exact Python/runtime dependency set used in the
# final image and allows feature trimming via build inputs.
#
# The local project package override (`plan`) is intentionally not defined here,
# because it carries repository-specific version metadata injection.
final: prev: let
  inherit (final) resolveBuildSystem;
in {
  django = prev.django.overrideAttrs (old: {
    postInstall = builtins.concatStringsSep "\n" [
      (old.postInstall or "")
      ''
        set -eu

        CONTRIB="$out/${final.python.sitePackages}/django/contrib"
        if [ -d "$CONTRIB" ]; then
          KEEP="staticfiles|contenttypes|__init__.py"
          ls -1 "$CONTRIB" | grep -vE "^($KEEP)$" | xargs -r -I {} rm -rf "$CONTRIB/{}"
        fi

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
}
