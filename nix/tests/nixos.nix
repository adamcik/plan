{module}: {
  name = "plan-nixos-service";

  nodes.machine = {
    config,
    lib,
    pkgs,
    ...
  }: {
    imports = [module];
    virtualisation.memorySize = 2048;
    services.postgresql = {
      enable = true;
      package = pkgs.postgresql_17;
      ensureDatabases = ["plan-alpha" "plan-beta"];
      ensureUsers = map (name: {
        inherit name;
        ensureDBOwnership = true;
      }) ["plan-alpha" "plan-beta"];
    };
    services.plan.instances = {
      alpha = {
        enable = true;
        port = 8081;
        processes = 1;
        environmentFile = "/run/plan-alpha.env";
        settings = {
          PGHOST = "/run/postgresql";
          PGDATABASE = "plan-alpha";
          PGUSER = "plan-alpha";
        };
        refreshCalendar = "2099-01-01";
      };
      beta = {
        enable = true;
        port = 8082;
        processes = 1;
        environmentFile = "/run/plan-beta.env";
        settings = {
          PGHOST = "/run/postgresql";
          PGDATABASE = "plan-beta";
          PGUSER = "plan-beta";
        };
      };
      unused.enable = false;
    };
    # Test-only secrets are created at runtime, exercising EnvironmentFile rather
    # than embedding credentials in the application's public environment.
    systemd.services =
      {
        plan-test-secrets = {
          wantedBy = ["multi-user.target"];
          serviceConfig.Type = "oneshot";
          script = ''
            umask 077
            echo DJANGO_SECRET_KEY=alpha-test-secret > /run/plan-alpha.env
            echo DJANGO_SECRET_KEY=beta-test-secret > /run/plan-beta.env
          '';
        };
      }
      // lib.genAttrs [
        "plan-alpha"
        "plan-beta"
        "plan-alpha-migrate"
        "plan-beta-migrate"
        "plan-alpha-check"
        "plan-beta-check"
        "plan-alpha-refresh"
      ] (_: {
        after = ["postgresql.service" "plan-test-secrets.service"];
        requires = ["postgresql.service" "plan-test-secrets.service"];
      });
    services.nginx = {
      enable = true;
      virtualHosts.localhost.locations = {
        "/_/static/".alias = "${config.services.plan.staticRoot}/";
        "/".proxyPass = "http://127.0.0.1:8081";
      };
    };
  };

  testScript = ''
    start_all()
    machine.wait_for_unit("postgresql.service")
    machine.wait_for_unit("plan-alpha.service")
    machine.wait_for_unit("plan-beta.service")
    machine.wait_for_unit("nginx.service")
    machine.fail("systemctl cat plan-unused.service")

    with subtest("migrations are explicit, not a web startup side effect"):
        for name in ("alpha", "beta"):
            machine.succeed(
                f"sudo -u postgres psql plan-{name} -Atc "
                "\"SELECT count(*) FROM pg_tables WHERE schemaname = 'public'\" | grep -x 0"
            )
            machine.fail(f"systemctl start plan-{name}-check.service")
            machine.succeed(f"systemctl start plan-{name}-migrate.service")
            machine.succeed(f"systemctl start plan-{name}-check.service")

    with subtest("both packaged web instances serve database-backed requests"):
        for port in (8081, 8082):
            machine.wait_until_succeeds(f"curl --fail http://127.0.0.1:{port}/+ > /dev/null")
        machine.succeed("curl --fail http://localhost/+ > /dev/null")
        machine.succeed("systemctl start plan-alpha-refresh.service")
        machine.wait_for_unit("plan-alpha-refresh.timer")
        machine.fail("systemctl cat plan-beta-refresh.timer")

    with subtest("instance users cannot read each other's state"):
        machine.succeed("sudo -u plan-alpha touch /var/lib/plan-alpha/marker")
        machine.succeed("sudo -u plan-alpha touch /var/cache/plan-alpha/marker")
        machine.fail("sudo -u plan-beta cat /var/lib/plan-alpha/marker")
        machine.fail("sudo -u plan-beta cat /var/cache/plan-alpha/marker")
        machine.succeed("test $(stat -c %a /run/plan-alpha.env) = 600")

    with subtest("the proxy serves matching static assets without the app"):
        machine.succeed("systemctl stop plan-alpha.service")
        machine.succeed("curl --fail http://localhost/_/static/CACHE/manifest.json > /tmp/manifest.json")
        machine.succeed("test -s /tmp/manifest.json")
        machine.succeed("systemctl start plan-alpha.service")
        machine.wait_until_succeeds("curl --fail http://localhost/+ > /dev/null")
        machine.succeed("test -f /var/lib/plan-alpha/marker")
  '';
}
