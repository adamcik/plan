# Manual Setup Steps

This document describes manual configuration steps that need to be performed in the GitHub repository settings.

## 1. GitHub Environment Setup

Create a GitHub Environment named `release`:

1. Go to repository Settings → Environments
2. Click "New environment"
3. Name it `release`
4. Configure deployment protection rules:
   - Select "Required reviewers" (optional, for added security)
   - Add deployment branches rule: "Selected branches"
   - Add pattern: `main`

This ensures the deploy job only runs for pushes to the main branch.

## 2. Branch Protection Rulesets

The branch protection rules are defined in `.github/rulesets/main-protection.json` but need to be imported:

1. Go to repository Settings → Rules → Rulesets
2. Click "New ruleset" → "Import a ruleset"
3. Select `.github/rulesets/main-protection.json`
4. Review and create the ruleset

The ruleset includes:
- Required 1 approval for PRs
- Required passing "Nix Flake Check" status
- Repository owner bypass for PR approval (but NOT for status checks)

## 3. GitHub Container Registry (GHCR) Settings

After the first successful image push, configure package access:

1. Go to https://github.com/users/adamcik/packages/container/plan/settings
2. Under "Danger Zone" → "Manage Actions access"
3. Add the `ci.yaml` workflow with write permission
4. Consider adding branch restrictions to only allow pushes from `main`

This prevents unauthorized workflows from pushing images.

## 4. Enable Renovate

If using GitHub's Renovate app:

1. Install the Renovate app from GitHub Marketplace
2. Grant access to the `adamcik/plan` repository
3. Renovate will automatically read `renovate.json` and start creating PRs

Alternatively, if using self-hosted Renovate, ensure it has access to the repository.

## 5. Secrets Configuration (Optional)

The CI workflow uses `GITHUB_TOKEN` which is automatically provided. No additional secrets are needed for basic functionality.

If you need additional secrets for deployment or testing:

1. Go to repository Settings → Secrets and variables → Actions
2. Add repository secrets as needed

## 6. Verify CI/CD Pipeline

After setup, verify the pipeline:

1. Create a test PR
2. Verify that "Nix Flake Check" runs and must pass
3. Verify that you can merge only after checks pass
4. After merging to main, verify that the deploy job runs
5. Check that the container image appears in GHCR

## Notes

- The `.github/CODEOWNERS` file is automatically recognized by GitHub
- The `release` environment gate ensures only authorized deployments
- Status check requirements cannot be bypassed, even by repository owner
- PR approval requirement CAN be bypassed by repository owner (solo-developer friendly)
