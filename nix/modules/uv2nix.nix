{
  lib,
  inputs,
  flake-parts-lib,
  ...
}: let
  inherit
    (flake-parts-lib)
    mkPerSystemOption
    ;
in {
  options = {
    perSystem = mkPerSystemOption {
      options.uv2nix = lib.mkOption {
        description = ''
          Project-level uv2nix configuration.
        '';

        type = lib.types.submodule {
          options = {
            workspaceRoot = lib.mkOption {
              type = lib.types.path;
              description = "Path to the root of the UV workspace";
            };

            python = lib.mkOption {
              type = lib.types.package;
              description = "Python package to use";
            };

            notEditablePackages = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              default = [];
              description = ''
                Names of local packages to *not* build editable.
                This is useful to build everything editable, except for packages
                which cannot be built editable.
              '';
            };

            pyprojectOverrides = lib.mkOption {
              type = lib.types.raw; # TODO: is there a better type for this?
              default = _final: _prev: {};
              description = ''
                Overlays with build fixups.

                See https://pyproject-nix.github.io/uv2nix/usage/hello-world.html?highlight=pyprojectOverrides#flakenix
              '';
            };

            venv = lib.mkOption {
              type = lib.types.package;
              description = "The python virtual environment for the project.";
            };
            depsVenv = lib.mkOption {
              type = lib.types.package;
              description = "The python virtual environment for the project.";
            };
            devVenv = lib.mkOption {
              type = lib.types.package;
              description = "The python virtual environment for the project.";
            };
            runtimeVenv = lib.mkOption {
              type = lib.types.package;
              description = "The python runtime virtual environment for the project.";
            };
            manageVenv = lib.mkOption {
              type = lib.types.package;
              description = "The python management-command virtual environment for the project.";
            };
          };
        };
      };
    };
  };

  config = {
    perSystem = {
      config,
      self',
      pkgs,
      ...
    }: let
      cfg = config.uv2nix;

      python = cfg.python;
      workspace = inputs.uv2nix.lib.workspace.loadWorkspace {
        workspaceRoot =
          # Workaround for https://github.com/pyproject-nix/uv2nix/issues/179
          /. + (builtins.unsafeDiscardStringContext cfg.workspaceRoot);
        config = {
          # These are locally override-built C-extension packages in workspace.nix.
          # Keep them on sdist so overrides control features and ABI consistently.
          no-binary-package = [
            "brotli"
            "lxml"
            "pillow"
            "pylibmc"
            "psycopg2"
            "reportlab"
          ];
        };
      };

      pyprojectToml = lib.importTOML (cfg.workspaceRoot + "/pyproject.toml");
      uvLock = inputs.uv2nix.lib.lock1.parseLock (lib.importTOML (cfg.workspaceRoot + "/uv.lock"));

      overlay = workspace.mkPyprojectOverlay {
        sourcePreference = "wheel";
      };

      pythonSet =
        (pkgs.callPackage inputs.pyproject-nix.build.packages {
          inherit python;
        }).overrideScope
        (
          lib.composeManyExtensions [
            inputs.pyproject-build-systems.overlays.default
            overlay
            cfg.pyprojectOverrides
          ]
        );

      localPackages = lib.filter inputs.uv2nix.lib.lock1.isLocalPackage uvLock.package;

      editablePackages =
        lib.filter (
          localPackage: !(lib.lists.elem localPackage.name cfg.notEditablePackages)
        )
        localPackages;

      # Create an overlay enabling editable mode for all local dependencies.
      editableOverlay = workspace.mkEditablePyprojectOverlay {
        root = "$REPO_ROOT";
        members = map (package: package.name) editablePackages;
      };

      # Override previous set with our overrideable overlay.
      editablePythonSet = pythonSet.overrideScope (
        lib.composeManyExtensions [editableOverlay]
      );

      project = pythonSet.${pyprojectToml.project.name};

      inherit (pkgs.callPackages inputs.pyproject-nix.build.util {}) mkApplication;
    in {
      uv2nix.devVenv = editablePythonSet.mkVirtualEnv "venv" workspace.deps.all;
      uv2nix.depsVenv = pythonSet.mkVirtualEnv "deps-venv" self'.packages.plan.dependencies;
      uv2nix.runtimeVenv = pythonSet.mkVirtualEnv "runtime-venv" workspace.deps.default;
      uv2nix.manageVenv = pythonSet.mkVirtualEnv "manage-venv" (
        workspace.deps.default
        // {
          ${pyprojectToml.project.name} = (workspace.deps.default.${pyprojectToml.project.name} or []) ++ ["scraper"];
        }
      );
      uv2nix.venv = config.uv2nix.runtimeVenv;

      packages.default = self'.packages.${project.pname};
      packages.${project.pname} = mkApplication {
        venv = config.uv2nix.runtimeVenv;
        package = project;
      };
    };
  };
}
