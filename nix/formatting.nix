{inputs, ...}: {
  imports = [inputs.treefmt-nix.flakeModule];

  perSystem = {pkgs, ...}: {
    treefmt = {
      projectRootFile = "flake.nix";

      programs = {
        alejandra.enable = true;
        oxfmt = {
          enable = true;
          excludes = [
            "plan/templates/**"
            "plan/static/js/lib/**"
          ];
        };
        # ruff-check.enable = true;
        ruff-format.enable = true;
      };

      settings.formatter = {
        djlint = {
          command = "${pkgs.djlint}/bin/djlint";
          includes = [
            "plan/templates/*.html"
            "plan/templates/**/*.html"
          ];
          options = ["--reformat" "--configuration" "pyproject.toml"];
        };
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
