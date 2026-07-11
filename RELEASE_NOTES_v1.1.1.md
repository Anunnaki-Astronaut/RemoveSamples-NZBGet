# RemoveSamples-NZBGet v1.1.1 — Draft GitHub Release Notes

> **Release status: active deployment verified on 2026-07-10. Final Git review, commit, and GitHub publication are still pending.**

## Safety hardening release

v1.1.1 fixes several destructive-behavior edge cases found during a Graphify-assisted code and safety review.

### Fixed

- **Test Mode is now a true dry run for quarantine expiration.** Old quarantine files are not purged while Test Mode is enabled.
- **Quarantine is excluded from candidate scanning.** Existing `_samples_quarantine` contents are no longer reprocessed on a later run.
- **Quarantine collisions fail safely.** Existing quarantined files are not overwritten.
- **A failed quarantine move retains the source directory.** The extension no longer removes a directory after an unsuccessful move.
- **Protected descendants now protect their parent candidate directory.** For example, `Sample/keep.srt` survives when `*.srt` is protected.
- **Relative Size % = 0 now disables relative detection** as documented. Absolute thresholds still apply when enabled.

### Validation completed locally

- 15/15 Python regression tests passed.
- Added regression coverage for every fixed safety case above.
- `ruff check main.py tests.py tools/unraid_smoke_test_v1111.py` passed.
- `manifest.json` validation and Python AST parsing passed.
- Graphify graph rebuild and health checks passed.
- Bandit reported no medium- or high-severity findings; two existing low-severity broad-exception findings remain for later hardening.
- The target NZBGet Docker container completed the disposable staging harness with **7/7 checks passed** against the staged v1.1.1 `main.py`.
- The active `/config/scripts/RemoveSamples` deployment was hash-verified in the target container, its manifest parsed successfully, and it reported version **1.1.1**.

### Release publication checklist

- [x] Local regression suite passed.
- [x] Target-container disposable harness passed: **7/7**.
- [x] Active deployment hash and manifest version verified in the target container.
- [ ] Review the final Git diff.
- [ ] Commit the release files and create the v1.1.1 GitHub release.

The disposable harness creates and alters files only under `/data/usenet/complete/_ka_removesamples_v1111_smoke`, refuses to reuse that root, and preserves it for inspection. See `tools/unraid_smoke_test_v1111.py` for the generated fixtures and assertions.

### Upgrade notes

- v1.1.1 is installed at `/config/scripts/RemoveSamples` and hash-verified in the target container.
- Keep **Quarantine Mode** enabled for the first real completed-download run.
- Keep **Test Mode** enabled while tuning thresholds or patterns.
- Do not use the `incomplete` directory for post-processing validation; NZBGet post-processing operates on completed download paths.

## Verification basis

- Local code review and isolated temporary-directory probes
- Automated Python regression suite
- Graphify AST relationship map
- NZBGet v23+ manifest contract validation
- Target LinuxServer NZBGet container staging validation and active deployment hash/manifest verification
