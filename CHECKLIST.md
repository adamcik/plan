# Pre-Deployment Checklist

Use this checklist before deploying the Nix-based infrastructure to production.

## Local Validation (if Nix is available)

- [ ] Run `nix flake check` - all checks pass
- [ ] Run `nix build .#container` - container builds successfully
- [ ] Run `nix develop` - dev shell works
- [ ] Run `nix fmt` - formatting works
- [ ] Verify container has no shell: `nix build .#container && docker load < result`
- [ ] Verify container runs as UID 1000

## GitHub Repository Setup

- [ ] Create "release" environment (Settings → Environments)
- [ ] Configure environment to allow deployments only from `main` branch
- [ ] Import branch ruleset from `.github/rulesets/main-protection.json`
- [ ] Verify ruleset is active
- [ ] Verify CODEOWNERS is recognized by GitHub

## CI/CD Validation

- [ ] Create a test PR
- [ ] Verify "Nix Flake Check" job runs
- [ ] Verify job must pass before merge is allowed
- [ ] Verify merge button is disabled while checks run
- [ ] Merge PR to main
- [ ] Verify deploy job runs on main
- [ ] Verify container image appears in GHCR

## GHCR Configuration

- [ ] Navigate to package settings after first push
- [ ] Configure "Manage Actions access"
- [ ] Restrict write access to `ci.yaml` workflow
- [ ] Add branch restriction to `main` only

## Renovate Setup

- [ ] Install Renovate app (or configure self-hosted)
- [ ] Grant access to repository
- [ ] Verify Renovate reads `renovate.json`
- [ ] Wait for first Renovate PR
- [ ] Verify Renovate PR triggers CI checks

## Security Verification

- [ ] Verify branch protection prevents force push
- [ ] Verify status checks cannot be bypassed
- [ ] Verify deployment requires "release" environment
- [ ] Verify container runs as non-root
- [ ] Verify container has no shell binaries
- [ ] Verify container includes only necessary dependencies

## Documentation Review

- [ ] Read NIX_README.md
- [ ] Read SETUP_GUIDE.md
- [ ] Read IMPLEMENTATION_SUMMARY.md
- [ ] Verify all manual steps are documented
- [ ] Verify examples are correct

## Developer Experience

- [ ] Clone repository fresh
- [ ] Run `nix develop` (with Nix installed)
- [ ] Verify all tools are available (uv, ruff, basedpyright)
- [ ] Run tests with pytest
- [ ] Make a code change
- [ ] Run `nix fmt`
- [ ] Verify change is formatted correctly

## Production Readiness

- [ ] Verify uWSGI configuration is appropriate for load
- [ ] Verify container has appropriate resource limits
- [ ] Verify logging is configured
- [ ] Verify SSL certificates are included (cacert)
- [ ] Verify Django settings for production
- [ ] Consider adding health check endpoint
- [ ] Consider adding metrics/monitoring
- [ ] Plan for database connectivity
- [ ] Plan for static file serving
- [ ] Plan for media file serving

## Optional Enhancements (Future)

- [ ] Add health check to container
- [ ] Add Prometheus metrics
- [ ] Add database migration job
- [ ] Add static file collection job
- [ ] Configure horizontal pod autoscaling (if using k8s)
- [ ] Add staging environment
- [ ] Add blue-green deployment
- [ ] Add rollback mechanism
- [ ] Add performance testing
- [ ] Add security scanning (already have CodeQL support via flake checks)

## Notes

- The container is minimal and distroless - no debugging tools included
- For debugging, use `nix develop` to enter a full environment
- The `release` environment gate is critical for security
- Status checks enforce quality even for repository owner
- Renovate PRs will require manual merge after CI passes

## Emergency Procedures

If something goes wrong:

1. **Failed deployment**: Check CI logs for errors
2. **Container won't start**: Check uWSGI logs, verify Django settings
3. **No access to merge**: Verify branch protection rules aren't too strict
4. **CI always failing**: Check if checks are too strict for the project
5. **Renovate broken**: Check renovate.json syntax and permissions

## Success Criteria

✅ CI passes on every PR  
✅ Merge button disabled until CI passes  
✅ Container builds successfully  
✅ Container deploys to GHCR  
✅ Container runs as non-root  
✅ Documentation is clear and complete  
✅ Solo developer can manage the entire pipeline  
