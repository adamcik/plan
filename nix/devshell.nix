{...}: {
  perSystem = {
    config,
    pkgs,
    ...
  }: {
    devShells.default = pkgs.mkShell {
      packages = with pkgs; [
        uv
        ruff
        basedpyright
        tombi
        djlint
        config.uv2nix.devVenv
        postgresql
      ];
      env = {
        "DJANGO_SETTINGS_MODULE" = "plan.settings.test";
      };

      shellHook = ''
        unset PYTHONPATH
        export REPO_ROOT=$(jj root 2> /dev/null || git rev-parse --show-toplevel)
        export PATH="${config.uv2nix.devVenv}/bin:$PATH"
      '';

      # motd = ''
      #   {202}Plan development environment{reset}
      #   All dependencies are pre-installed via Nix (uv2nix).
      #   You do not need to run 'uv sync' in this shell.
      #
      #   PGHOST is dynamically set to your working directory (see shellHook).
      #
      #
      #    {bold}Available commands:{reset}
      #      ./manage.py runserver
      #      ruff check .                - Lint Python code
      #      basedpyright                - Type check Python code
      #
      #    {bold}To run tests:{reset}
      #      nix develop --command "./manage.py test"
      #
      #    Tests automatically run against an ephemeral PostgreSQL instance.
      # '';
    };

    devShells.playwright = pkgs.mkShell {
      packages = with pkgs; [
        nodejs
        playwright-driver
        playwright-mcp
      ];

      env = {
        PLAYWRIGHT_BROWSERS_PATH = "${pkgs.playwright-driver.browsers}";
        PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS = "true";

        OPENCODE_CONFIG_CONTENT = builtins.toJSON {
          mcp = {
            playwright-mcp = {
              type = "local";
              command = ["mcp-server-playwright"];
              enabled = true;
            };
          };
        };
      };
    };
  };
}
