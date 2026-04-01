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
        taplo
        config.uv2nix.devVenv
        # self'.packages.start-db
        postgresql
      ];
      env = {
        "DJANGO_SETTINGS_MODULE" = "plan.settings.test";
        # FIXME: uv never download...
        "PGHOST" = "$PWD/data/pgdata";
        "PGDATABASE" = "plan";
      };

      shellHook = ''
        unset PYTHONPATH
        export REPO_ROOT=$(jj root 2> /dev/null || git rev-parse --show-toplevel)
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
      #    {bold}To run tests with Postgres:{reset}
      #      DJANGO_SETTINGS_MODULE=plan.settings.test nix develop --command "./manage.py test"
      #
      #    This ensures tests run on your running Postgres instance. No extra scripts or env setup needed.
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
