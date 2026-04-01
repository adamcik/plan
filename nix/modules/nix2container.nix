{
  lib,
  flake-parts-lib,
  ...
}: let
  inherit (flake-parts-lib) mkPerSystemOption;
in {
  options = {
    perSystem = mkPerSystemOption {
      options.nix2container = lib.mkOption {
        description = "Project-level nix2container configuration.";
        type = lib.types.submodule {
          options = {
            imageConfig = lib.mkOption {
              type = lib.types.raw;
              default = {};
              description = "OCI image config (entrypoint, env, ports, etc).";
            };
            copyToRoot = lib.mkOption {
              type = lib.types.listOf lib.types.package;
              default = [];
              description = "Packages/closures to copy into root of image.";
            };
            layers = lib.mkOption {
              type = lib.types.listOf lib.types.package;
              default = [];
              description = "nix2container layering closures.";
            };
            name = lib.mkOption {
              type = lib.types.str;
              description = "Container image name.";
            };
            tag = lib.mkOption {
              type = lib.types.str;
              default = "latest";
              description = "Container image tag/version.";
            };
            maxLayers = lib.mkOption {
              type = lib.types.int;
              default = 1;
              description = "Maximum image layers (see nix2container docs).";
            };
          };
        };
      };
    };
  };

  config = {
    perSystem = {
      config,
      pkgs,
      inputs',
      ...
    }: let
      cfg = config.nix2container;
      image = inputs'.nix2container.packages.nix2container.buildImage {
        inherit (cfg) name tag;
        maxLayers = cfg.maxLayers;
        copyToRoot = pkgs.buildEnv {
          name = cfg.name + "-root";
          paths = cfg.copyToRoot;
          pathsToLink = ["/bin" "/lib" "/share" "/etc" "/app"];
        };
        config = cfg.imageConfig;
        layers = cfg.layers;
      };
    in {
      packages.image = image;
    };
  };
}
