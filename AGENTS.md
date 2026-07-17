# Agent Guide (Nix-first workflow)

This repo is Nix-first. Use Nix entrypoints for formatting and full validation.

## Required workflow

- Run `nix fmt` before finalizing code changes.
- Run `nix flake check` to validate changes.
- Prefer `nix develop` when you need an interactive environment.
- Do not rely on globally installed Python tools.

## Tests and database behavior

- Quick test runs use `pytest`.
- Pytest provisions an ephemeral PostgreSQL instance automatically.
- Full test verification should still use `nix flake check`.

## Pytest settings expectations

- Test checks run with `DJANGO_SETTINGS_MODULE=plan.settings`.
- Keep changes compatible with ephemeral Postgres-backed test runs.

## Practical commands

- Format: `nix fmt`
- Full validation: `nix flake check`
- Interactive shell: `nix develop`
- Django migrations (inside devshell): `nix develop -c django-admin makemigrations <app>`

## Version control + Nix visibility

- Ensure newly created files are tracked before running Nix checks/builds.
- For Git workflows, stage new files (especially migrations) with `git add`.
- For Jujutsu workflows, track new files with `jj file track` so Nix sees them in the working tree.

## Useful targeted builds

- Run only pytest tests check:
  - `nix build .#checks.x86_64-linux.django-test`
- Run only Django system check:
  - `nix build .#checks.x86_64-linux.django-check`
- Run only formatting/lint check:
  - `nix build .#checks.x86_64-linux.treefmt`
- Build app package:
  - `nix build .#packages.x86_64-linux.plan`
- Build container image artifact:
  - `nix build .#packages.x86_64-linux.image`

## Current flake outputs to know

- Checks: `django-check`, `django-test`, `treefmt`
- Packages: `plan`/`default`, `image`
- Dev shells: `default`, `playwright`
