{...}: {
  imports = [./modules/nix2container.nix];

  perSystem = {
    config,
    pkgs,
    inputs',
    ...
  }: let
    nix2containerPkgs = inputs'.nix2container.packages.nix2container;
    uwsgiPkg = pkgs.uwsgi.override {
      python3 = config.uv2nix.python;
      plugins = ["python3"];
    };
    manageScript = pkgs.writeShellScriptBin "manage" ''
      export DJANGO_SETTINGS_MODULE="''${DJANGO_SETTINGS_MODULE:-plan.settings.container}"
      export PLAN_BASE_DIR="''${PLAN_BASE_DIR:-/var/lib/plan}"
      exec ${pkgs.lib.getExe' config.uv2nix.manageVenv "python3"} -m django "$@"
    '';
    staticAssets =
      pkgs.runCommand "plan-static-assets" {
        nativeBuildInputs = [config.uv2nix.runtimeVenv];
        src = ../.;
      } ''
        mkdir -p "$TMPDIR/static"

        cd "$src"
        export DJANGO_SETTINGS_MODULE="plan.settings.container"
        export PLAN_BASE_DIR="$TMPDIR"
        export DJANGO_SECRET_KEY="nix-build-static"
        python manage.py collectstatic --noinput

        mkdir -p "$out/static"
        cp -r "$TMPDIR/static"/. "$out/static"
      '';
  in {
    nix2container = {
      name = "plan";
      tag = "latest";

      imageConfig = {
        Cmd = [
          (pkgs.lib.getExe uwsgiPkg)
          "--plugin"
          "python3"
          "--log-format"
          "%(addr) - %(user) [%(ltime)] \"%(method) %(uri) %(proto)\" %(status) %(size) \"%(referer)\" \"%(uagent)\""
          "--ignore-sigpipe"
          "--ignore-write-errors"
          "--disable-write-exception"
          "--http"
          "0.0.0.0:8080"
          "--env"
          "DJANGO_SETTINGS_MODULE=plan.settings.container"
          "--env"
          "PLAN_BASE_DIR=/var/lib/plan"
          "--static-map"
          "/static/CACHE=/var/lib/plan/static/CACHE"
          "--static-map"
          "/static=${staticAssets}/static"
          "--module"
          "plan.wsgi"
          "--virtualenv"
          "${config.uv2nix.runtimeVenv}"
          "--master"
          "--processes"
          "4"
          "--threads"
          "4"
          "--show-config"
          "--need-app"
        ];
        WorkingDir = "/app";
        User = "1234:1234";
        ExposedPorts = {"8080/tcp" = {};};
        Env = ["SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"];
      };

      layers = let
        baseLayer = nix2containerPkgs.buildLayer {
          deps = [
            uwsgiPkg
            config.uv2nix.python
          ];
          copyToRoot = [
            (pkgs.buildEnv {
              name = "plan-root-bin";
              paths = [manageScript];
              pathsToLink = ["/bin"];
            })
          ];
        };
        depsLayer = nix2containerPkgs.buildLayer {
          deps = [config.uv2nix.depsVenv];
          layers = [baseLayer];
        };
        appLayer = nix2containerPkgs.buildLayer {
          deps = [
            config.uv2nix.runtimeVenv
            config.uv2nix.manageVenv
            staticAssets
          ];
          layers = [baseLayer depsLayer];
        };
      in [
        baseLayer
        depsLayer
        appLayer
      ];
    };
  };
}
