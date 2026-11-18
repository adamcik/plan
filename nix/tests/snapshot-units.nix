{
  module,
  pkgs,
}: let
  evaluated = import (pkgs.path + "/nixos/lib/eval-config.nix") {
    system = pkgs.stdenv.hostPlatform.system;
    modules = [
      module
      {
        services.plan.instances.alpha = {
          enable = true;
          snapshots.spring = {
            year = 2030;
            type = "spring";
            jobs = ["courses"];
          };
        };
        system.stateVersion = "26.05";
      }
    ];
  };
  cfg = evaluated.config;
  unit = cfg.systemd.services.plan-alpha-snapshot-spring;
  timer = cfg.systemd.timers.plan-alpha-snapshot-spring;
in
  assert unit.serviceConfig.Type == "oneshot";
  assert unit.serviceConfig.User == "plan-alpha";
  assert unit.restartIfChanged == false;
  assert pkgs.lib.hasInfix "run_semester_snapshot --year 2030 --type spring" unit.serviceConfig.ExecStart;
  assert pkgs.lib.hasInfix "/var/lib/plan-alpha/snapshots/spring" unit.serviceConfig.ExecStart;
  assert timer.timerConfig.OnCalendar == "weekly";
  assert timer.timerConfig.Persistent;
  assert pkgs.lib.hasInfix "--capture ntnu --job courses" unit.serviceConfig.ExecStart;
  assert !(builtins.hasAttr "plan-alpha-refresh" cfg.systemd.timers);
    pkgs.runCommand "plan-snapshot-units" {} ''touch "$out"''
