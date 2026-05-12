{pkgs}: let
  # Canonical runtime Python for this repo.
  #
  # We intentionally avoid `withMinimalDeps=true`: once we re-enable required
  # components (openssl/expat/mpdecimal), CPython's minimal-build
  # allowed-reference guard rejects those runtime references.
  #
  # Instead, we keep equivalent slimming explicit with stable override flags
  # and avoid fragile postInstall surgery.
  python = pkgs.python312.override {
    bluezSupport = false;
    stripConfig = true;
    stripIdlelib = true;
    stripTests = true;
    stripTkinter = true;

    rebuildBytecode = false;
    stripBytecode = true;

    readline = null;
    ncurses = null;
    gdbm = null;
    withSqlite = true;
  };

  # Keep uwsgi aligned with the exact Python derivation above and disable
  # optional integrations we do not use to reduce runtime closure size.
  uwsgi = pkgs.uwsgi.override {
    python3 = python;
    plugins = ["python3"];
    withPAM = false;
    withSystemd = false;
    withCap = false;
  };
in {
  inherit python uwsgi;
}
