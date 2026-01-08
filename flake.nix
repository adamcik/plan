{
  description = "Plan - Hardened Nix-Python Deployment Stack";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
    treefmt-nix.url = "github:numtide/treefmt-nix";
    treefmt-nix.inputs.nixpkgs.follows = "nixpkgs";
    uv2nix.url = "github:pyproject-nix/uv2nix";
    uv2nix.inputs.nixpkgs.follows = "nixpkgs";
    pyproject-nix.url = "github:pyproject-nix/pyproject.nix";
    pyproject-nix.inputs.nixpkgs.follows = "nixpkgs";
    nix2container.url = "github:nlewo/nix2container";
    nix2container.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = inputs @ {
    flake-parts,
    nixpkgs,
    ...
  }:
    flake-parts.lib.mkFlake {inherit inputs;} {
      systems = ["x86_64-linux" "aarch64-linux"];

      imports = [
        inputs.treefmt-nix.flakeModule
      ];

      perSystem = {
        config,
        self',
        inputs',
        pkgs,
        system,
        lib,
        ...
      }: let
        # Load uv workspace
        workspace = inputs'.uv2nix.lib.workspace.loadWorkspace {
          workspaceRoot = ./.;
        };

        # Create overlay with Python packages from uv.lock
        overlay = workspace.mkPyprojectOverlay {
          sourcePreference = "wheel";
        };

        # Python with our overlay applied
        python = pkgs.python3.override {
          packageOverrides = overlay;
        };

        # Create virtual environment with all dependencies
        venv = python.pkgs.mkVirtualEnv "plan-venv" workspace.deps.default;

        # Application source
        appSrc = pkgs.stdenv.mkDerivation {
          name = "plan-source";
          src = ./.;
          installPhase = ''
            mkdir -p $out
            cp -r plan manage.py static $out/
            # Only copy cache if it exists
            if [ -d cache ]; then
              cp -r cache $out/
            fi
          '';
        };

        # uWSGI with Python plugin
        uwsgi = pkgs.uwsgi.override {
          plugins = ["python3"];
          python3 = pkgs.python3;
        };

        # uWSGI configuration
        uwsgiConfig = pkgs.writeText "uwsgi.ini" ''
          [uwsgi]
          module = plan.wsgi:application
          master = true
          processes = 4
          threads = 2
          enable-threads = true
          http-socket = :8000
          vacuum = true
          die-on-term = true
          need-app = true
          
          # Python configuration
          chdir = ${appSrc}
          pythonpath = ${appSrc}
          home = ${venv}
          
          # Logging
          log-format = %(addr) - %(user) [%(ltime)] "%(method) %(uri) %(proto)" %(status) %(size) "%(referer)" "%(uagent)"
        '';

        # /etc files for container
        etcFiles = pkgs.runCommand "etc-files" {} ''
          mkdir -p $out/etc
          cat > $out/etc/passwd <<EOF
          appuser:x:1000:1000:Application User:/app:/noshell
          EOF
          cat > $out/etc/group <<EOF
          appuser:x:1000:
          EOF
          chmod 644 $out/etc/passwd $out/etc/group
        '';

        # Container image
        containerImage = inputs'.nix2container.packages.nix2container.buildImage {
          name = "plan";
          tag = "latest";
          maxLayers = 100;

          copyToRoot = [
            (pkgs.buildEnv {
              name = "plan-root";
              paths = [
                uwsgi
                venv
                pkgs.cacert
                appSrc
                etcFiles
              ];
              pathsToLink = ["/bin" "/lib" "/share" "/etc"];
            })
          ];

          config = {
            Cmd = [
              "${uwsgi}/bin/uwsgi"
              "--ini"
              "${uwsgiConfig}"
            ];
            WorkingDir = "${appSrc}";
            User = "1000:1000";
            Env = [
              "DJANGO_SETTINGS_MODULE=plan.settings"
              "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
              "PYTHONPATH=${appSrc}"
            ];
            ExposedPorts = {
              "8000/tcp" = {};
            };
          };
        };
      in {
        # Development shell
        devShells.default = pkgs.mkShell {
          packages = [
            venv
            pkgs.uv
            pkgs.ruff
            pkgs.basedpyright
            uwsgi
          ];

          shellHook = ''
            export DJANGO_SETTINGS_MODULE=plan.settings.local
            # Add both venv and current directory to PYTHONPATH
            export PYTHONPATH="${venv}/${venv.python.sitePackages}"
            [ -n "$PWD" ] && export PYTHONPATH="$PYTHONPATH:$PWD"
            echo "Plan development environment"
            echo "Python: ${venv.python}/bin/python"
            echo "Virtual env: ${venv}"
            echo ""
            echo "Available commands:"
            echo "  python manage.py runserver  - Run development server"
            echo "  ruff check .                - Lint Python code"
            echo "  basedpyright                - Type check Python code"
            echo "  pytest                      - Run tests"
          '';
        };

        # Packages and scripts
        packages = {
          default = containerImage;
          container = containerImage;
          
          # Script to load container to docker and push to registry
          pushToRegistry = pkgs.writeShellScriptBin "push-to-registry" ''
            set -euo pipefail
            
            IMAGE_NAME="''${1:-ghcr.io/adamcik/plan}"
            IMAGE_TAG="''${2:-latest}"
            
            echo "Loading container image to Docker..."
            ${containerImage.copyToDockerDaemon}
            
            echo "Tagging image as $IMAGE_NAME:$IMAGE_TAG"
            ${pkgs.docker}/bin/docker tag ${containerImage.imageName}:${containerImage.imageTag} "$IMAGE_NAME:$IMAGE_TAG"
            
            echo "Pushing to registry..."
            ${pkgs.docker}/bin/docker push "$IMAGE_NAME:$IMAGE_TAG"
            
            echo "Successfully pushed $IMAGE_NAME:$IMAGE_TAG"
          '';
        };

        # Checks for CI
        checks = {
          # Run pytest
          pytest = pkgs.runCommand "pytest" {
            nativeBuildInputs = [venv];
          } ''
            export PYTHONPATH=${venv}/${venv.python.sitePackages}:${./.}
            export DJANGO_SETTINGS_MODULE=plan.settings.test
            cd ${./.}
            ${venv}/bin/python -m pytest plan/
            touch $out
          '';

          # uWSGI smoke test
          uwsgi-smoke = pkgs.runCommand "uwsgi-smoke-test" {
            nativeBuildInputs = [uwsgi venv];
          } ''
            export PYTHONPATH=${venv}/${venv.python.sitePackages}:${appSrc}
            export DJANGO_SETTINGS_MODULE=plan.settings
            cd ${appSrc}
            ${uwsgi}/bin/uwsgi --setup-only --ini ${uwsgiConfig}
            touch $out
          '';

          # Formatting check
          formatting = config.treefmt.build.check self';
        };

        # Formatting configuration
        treefmt = {
          projectRootFile = "flake.nix";
          programs = {
            alejandra.enable = true; # Nix formatter
            ruff = {
              enable = true;
              format = true; # Use ruff format
            };
          };
          settings.formatter = {
            # Exclude common non-source directories
            excludes = ["*.pyc" "__pycache__" "*.sqlite" ".direnv"];
          };
        };

        # Formatter
        formatter = config.treefmt.build.wrapper;
      };
    };
}
