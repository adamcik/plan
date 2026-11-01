{self, ...}: {
  flake.nixosModules.default = import ./nixos-module.nix {inherit self;};

  perSystem = {pkgs, ...}: {
    checks.nixos-service = pkgs.testers.runNixOSTest (import ./tests/nixos.nix {
      module = self.nixosModules.default;
    });
  };
}
