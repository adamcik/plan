# 01 — Establish pytest PostgreSQL test platform

**What to build:** Contributors and Nix checks can run the test suite through pytest with the same automatically provisioned isolated PostgreSQL server, without requiring an externally running database.

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] Running pytest in the development environment provisions and tears down an isolated PostgreSQL server automatically.
- [x] The Nix test check runs pytest with isolated temporary and cache paths.
- [x] The existing suite remains runnable through pytest while later tickets complete its conversion.

## Comments

Resolved by `6872c2b` (`test: run suite with pytest`).
