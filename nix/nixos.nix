{self, ...}: {
  flake.nixosModules.default = import ./nixos-module.nix {inherit self;};

  perSystem = {pkgs, ...}: {
    checks.snapshot-units = import ./tests/snapshot-units.nix {
      inherit pkgs;
      module = self.nixosModules.default;
    };
    checks.nixos-service = pkgs.testers.runNixOSTest (import ./tests/nixos.nix {
      module = self.nixosModules.default;
    });
  };
}
