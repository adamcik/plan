{inputs, ...}: {
  imports = [inputs.treefmt-nix.flakeModule];

  perSystem = {...}: {
    treefmt = {
      projectRootFile = "flake.nix";

      programs = {
        alejandra.enable = true;
        # ruff-check.enable = true;
        ruff-format.enable = true;
        taplo.enable = true;
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
