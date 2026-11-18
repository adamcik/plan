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
        services.plan.instances.beta = {
          enable = true;
          snapshots.fall = {
            year = 2030;
            type = "fall";
            automaticImport = true;
            maxDeletePercent = 5;
            calendar = "daily";
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
  assert !(pkgs.lib.hasInfix "--import-snapshot" unit.serviceConfig.ExecStart);
  assert pkgs.lib.hasInfix "--import-snapshot --create --max-delete-percent 5" cfg.systemd.services.plan-beta-snapshot-fall.serviceConfig.ExecStart;
  assert cfg.systemd.timers.plan-beta-snapshot-fall.timerConfig.OnCalendar == "daily";
  assert pkgs.lib.hasInfix "--capture ntnu --job courses" unit.serviceConfig.ExecStart;
  assert !(builtins.hasAttr "plan-alpha-refresh" cfg.systemd.timers);
    pkgs.runCommand "plan-snapshot-units" {} ''touch "$out"''
