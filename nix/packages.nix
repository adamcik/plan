{pkgs}: let
  # Use nixpkgs' interpreter unchanged so deployments can reuse its binary cache.
  python = pkgs.python312;

  # uWSGI's Python plugin must use the application's interpreter, not the
  # nixpkgs default Python version.
  uwsgi = pkgs.uwsgi.override {
    python3 = python;
    plugins = ["python3"];
  };
in {
  inherit python uwsgi;
}
