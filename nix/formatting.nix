{inputs, ...}: {
  imports = [inputs.treefmt-nix.flakeModule];

  perSystem = {pkgs, ...}: {
    treefmt = {
      projectRootFile = "flake.nix";

      programs = {
        alejandra.enable = true;
        # ruff-check.enable = true;
        ruff-format.enable = true;
      };

      settings.formatter = {
        tombi-format = {
          command = "${pkgs.tombi}/bin/tombi";
          includes = ["*.toml"];
          options = ["format" "--offline"];
        };
        tombi-lint = {
          command = "${pkgs.tombi}/bin/tombi";
          includes = ["*.toml"];
          options = ["lint" "--offline"];
        };
      };

      # settings.formatter.excludes = [
      #   "*.pyc"
      #   "__pycache__"
      #   "*.sqlite"
      #   ".direnv"
      # ];
    };
  };
}
