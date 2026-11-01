{
  inputs,
  self,
  ...
}: {
  imports = [./modules/nix2container.nix];

  perSystem = {
    config,
    self',
    pkgs,
    inputs',
    ...
  }: let
    projectPkgs = import ./packages.nix {inherit pkgs;};
    nix2containerPkgs = inputs'.nix2container.packages.nix2container;
    overrideMetadata = builtins.fromJSON (builtins.readFile inputs.build-overrides);
    buildRevision =
      if ((overrideMetadata.revision or null) != null)
      then overrideMetadata.revision
      else (self.rev or null);
    fallbackCreated = let
      d = self.lastModifiedDate or "";
    in
      if d == "" || builtins.stringLength d < 14
      then "0001-01-01T00:00:00Z"
      else "${builtins.substring 0 4 d}-${builtins.substring 4 2 d}-${builtins.substring 6 2 d}T${builtins.substring 8 2 d}:${builtins.substring 10 2 d}:${builtins.substring 12 2 d}Z";
    serveScript = self'.packages.plan-web;
    manageScript = self'.packages.plan-manage;
    staticAssets = self'.packages.plan-static;

    # Keep fallback runtime paths writable for rootless runs without host mounts.
    # Most deployments bind-mount /var/lib/plan, /var/cache/plan, and /run/uwsgi
    # with tighter host-managed ownership/permissions, which override these modes.
    runtimeDirs = pkgs.runCommand "plan-runtime-dirs" {} ''
      for path in \
        "$out/run/uwsgi" \
        "$out/var/lib/plan" \
        "$out/var/cache/plan" \
        "$out/var/cache/plan/default" \
        "$out/var/cache/plan/disk" \
        "$out/var/cache/plan/scraper"
      do
        install -d -m 1777 "$path"
      done
      install -d -m 1777 "$out/tmp"
    '';

    staticLink = pkgs.runCommand "plan-static-link" {} ''
      install -d -m 0755 "$out/var/lib/plan"
      ln -s "${staticAssets}/static" "$out/var/lib/plan/static"
    '';
  in {
    nix2container = {
      name = "ghcr.io/adamcik/plan";
      tag = "latest";
      created =
        if ((overrideMetadata.created or null) != null)
        then overrideMetadata.created
        else fallbackCreated;

      imageConfig = {
        Cmd = [(pkgs.lib.getExe serveScript)];
        WorkingDir = "/app";
        User = "65532:65532";
        Env =
          [
            "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
            "PYTHONDONTWRITEBYTECODE=1"
            "DJANGO_SETTINGS_MODULE=plan.settings"
            "PLAN_BASE_DIR=/var/lib/plan"
            "PLAN_CACHE_DIR=/var/cache/plan"
            "PLAN_SCRAPER_CACHE_KEY_PREFIX=container-scraper"
            "PLAN_UWSGI_STATIC_ROOT=/var/lib/plan/static"
            "STATIC_URL=/_/static/"
            "PLAN_UWSGI_LISTENER=http"
            "PLAN_UWSGI_HTTP=0.0.0.0:8080"
            "PLAN_UWSGI_SOCKET=/run/uwsgi/uwsgi.sock"
            "PLAN_UWSGI_PROCESSES=4"
            "PLAN_UWSGI_THREADS=1"
            "OTEL_VCS_REVISION=${
              if buildRevision != null
              then buildRevision
              else "unknown"
            }"
          ]
          ++ pkgs.lib.optional ((overrideMetadata.version or null) != null) "SENTRY_RELEASE=plan@${overrideMetadata.version}";
        Labels = let
          created =
            if ((overrideMetadata.created or null) != null)
            then overrideMetadata.created
            else fallbackCreated;
        in
          {
            "org.opencontainers.image.created" = created;
            "org.opencontainers.image.description" = "Timetable generator for educational institutions.";
            "org.opencontainers.image.source" = "https://github.com/adamcik/plan";
            "org.opencontainers.image.title" = "plan";
          }
          // pkgs.lib.optionalAttrs (buildRevision != null) {
            "org.opencontainers.image.revision" = buildRevision;
          }
          // pkgs.lib.optionalAttrs ((overrideMetadata.version or null) != null) {
            "org.opencontainers.image.version" = overrideMetadata.version;
          };
      };

      layers = let
        baseLayer = nix2containerPkgs.buildLayer {
          deps = [
            projectPkgs.uwsgi
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
        metadataLayer = nix2containerPkgs.buildLayer {
          copyToRoot = [
            (pkgs.buildEnv {
              name = "plan-root-bin";
              paths = [
                manageScript
                serveScript
              ];
              pathsToLink = ["/bin"];
            })
            staticLink
            runtimeDirs
          ];
          layers = [baseLayer depsLayer appLayer];
        };
      in [
        baseLayer
        depsLayer
        appLayer
        metadataLayer
      ];
    };
  };
}
