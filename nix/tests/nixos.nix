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
        processes = 1;
        environmentFile = "/run/plan-alpha.env";
        settings = {
          DJANGO_ALLOWED_HOSTS = "alpha.localhost";
          PGHOST = "/run/postgresql";
          PGDATABASE = "plan-alpha";
          PGUSER = "plan-alpha";
        };
        refreshCalendar = "2099-01-01";
      };
      beta = {
        enable = true;
        processes = 1;
        environmentFile = "/run/plan-beta.env";
        settings = {
          DJANGO_ALLOWED_HOSTS = "beta.localhost";
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
      virtualHosts = lib.genAttrs ["alpha.localhost" "beta.localhost"] (host: let
        name = lib.removeSuffix ".localhost" host;
      in {
        locations."/_/static/".alias = "${config.services.plan.staticRoot}/";
        locations."/".extraConfig = ''
          include ${pkgs.nginx}/conf/uwsgi_params;
          uwsgi_pass unix:${config.services.plan.instances.${name}.socketPath};
        '';
      });
    };
    users.users.nginx.extraGroups =
      map (instance: instance.socketGroup)
      (lib.attrValues (lib.filterAttrs (_: instance: instance.enable) config.services.plan.instances));
  };

  testScript = ''
    start_all()
    machine.wait_for_unit("postgresql.service")
    machine.wait_for_unit("plan-alpha.service")
    machine.wait_for_unit("plan-beta.service")
    machine.wait_for_unit("nginx.service")
    machine.fail("systemctl cat plan-unused.service")
    for name in ("alpha", "beta"):
        machine.wait_until_succeeds(f"test -S /run/plan-{name}/uwsgi.sock", timeout=60)

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
        for name in ("alpha", "beta"):
            machine.wait_until_succeeds(
                f"curl --fail -H 'Host: {name}.localhost' http://127.0.0.1/+ > /dev/null",
                timeout=60,
            )
            machine.succeed(f"test -S /run/plan-{name}/uwsgi.sock")
            machine.succeed(f"test $(stat -c %a /run/plan-{name}/uwsgi.sock) = 660")
            machine.succeed(f"test $(stat -c %G /run/plan-{name}/uwsgi.sock) = plan-{name}-proxy")
        machine.fail("ss -ltnp | grep uwsgi")
        machine.succeed("systemctl start plan-alpha-refresh.service")
        machine.wait_for_unit("plan-alpha-refresh.timer")
        machine.fail("systemctl cat plan-beta-refresh.timer")

    with subtest("instance users cannot read each other's state"):
        machine.succeed("sudo -u plan-alpha touch /var/lib/plan-alpha/marker")
        machine.succeed("sudo -u plan-alpha touch /var/cache/plan-alpha/marker")
        machine.fail("sudo -u plan-beta cat /var/lib/plan-alpha/marker")
        machine.fail("sudo -u plan-beta cat /var/cache/plan-alpha/marker")
        machine.fail("sudo -u nginx cat /var/lib/plan-alpha/marker")
        machine.fail("sudo -u nginx cat /var/cache/plan-alpha/marker")
        machine.fail("sudo -u plan-beta test -w /run/plan-alpha/uwsgi.sock")
        machine.fail("sudo -u nobody test -w /run/plan-alpha/uwsgi.sock")
        machine.succeed("test $(stat -c %a /run/plan-alpha.env) = 600")

    with subtest("the proxy serves matching static assets without the app"):
        machine.succeed("systemctl stop plan-alpha.service")
        machine.succeed("curl --fail -H 'Host: alpha.localhost' http://127.0.0.1/_/static/CACHE/manifest.json > /tmp/manifest.json")
        machine.succeed("test -s /tmp/manifest.json")
        machine.succeed("systemctl start plan-alpha.service")
        machine.wait_until_succeeds("curl --fail -H 'Host: alpha.localhost' http://127.0.0.1/+ > /dev/null")
        machine.succeed("test -f /var/lib/plan-alpha/marker")
  '';
}
