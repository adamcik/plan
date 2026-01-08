# Nix Deployment Stack

This repository uses a hardened Nix-based deployment pipeline for reproducible builds and secure container images.

## Quick Start

### Development

```bash
# Enter development shell
nix develop

# Run development server
python manage.py runserver

# Run tests
pytest

# Format code
nix fmt

# Type check
basedpyright
```

### Building

```bash
# Build container image
nix build .#container

# Run all checks (tests, smoke tests, formatting)
nix flake check
```

### Deployment

Container images are automatically built and pushed to GHCR when:
- Changes are pushed to the `main` branch
- A GitHub Release is published

The `release` environment gates deployment to ensure only authorized pushes from `main` branch.

## Architecture

### Components

- **flake-parts**: Modular flake architecture supporting x86_64-linux and aarch64-linux
- **uv2nix**: Deterministic Python environment from uv.lock
- **pyproject.nix**: Python project integration
- **nix2container**: Layered, minimal OCI images
- **uWSGI**: Production WSGI server
- **treefmt-nix**: Unified formatting (Alejandra for Nix, Ruff for Python)

### Security Features

- **Distroless**: No shell, package manager, or unnecessary utilities in container
- **Non-privileged**: Runs as `appuser` (UID 1000)
- **Minimal closure**: Only cacert, uWSGI, Python, and app dependencies
- **Layered**: Each Nix store path is a separate layer for efficient caching

### CI/CD

- **nix-fast-build**: Parallel evaluation and building
- **magic-nix-cache**: Binary caching for fast CI runs
- **Branch protection**: Status checks must pass before merge
- **Environment protection**: `release` environment restricted to main branch

## Repository Structure

```
.
├── flake.nix                 # Nix flake definition
├── pyproject.toml            # Python project metadata
├── uv.lock                   # Locked Python dependencies
├── .github/
│   ├── workflows/
│   │   └── ci.yaml          # CI/CD pipeline
│   ├── rulesets/
│   │   └── main-protection.json  # Branch protection rules
│   └── CODEOWNERS           # Code ownership
└── renovate.json            # Dependency update configuration
```

## Governance

### Branch Protection

The `main` branch is protected by:
- Required approval for all PRs (1 reviewer)
- Required passing status check: "Nix Flake Check"
- Repository owner can bypass PR approval requirement
- Status checks must always pass (no bypass)

### Package Registry

GHCR package settings should be manually configured to:
- Restrict write access to the `ci.yaml` workflow
- Only allow pushes from `main` branch

### Dependency Updates

Renovate automatically creates PRs for:
- Nix input updates (weekly)
- Python dependency updates (weekly)

Updates are validated by CI and can be merged with a single approval.

## Success Criteria

✅ Developer can run `nix develop` for instant LSP environment
✅ `nix build .#container` produces minimal image (~50-100MB)
✅ Renovate PRs automatically validated by CI
✅ Images only pushed to GHCR when `release` environment requirements satisfied
✅ All checks (tests, smoke tests, formatting) run in `nix flake check`
