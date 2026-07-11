# RemoveSamples-NZBGet v1.1.1

> **Release validation complete:** controlled Test Mode, Block Import, and Quarantine Mode observations passed on the active NZBGet system on 2026-07-11. The final Block Import logging refinement passed the target-container disposable harness 8/8, was deployed with a verified rollback backup, and passed active-container hash, JSON, and Python syntax verification.

## Safety hardening release

v1.1.1 fixes several destructive-behavior edge cases found during a automated code and safety review.

### Fixed

- **Test Mode is now a true dry run for quarantine expiration.** Old quarantine files are not purged while Test Mode is enabled.
- **Quarantine is excluded from candidate scanning.** Existing `_samples_quarantine` contents are no longer reprocessed on a later run.
- **Quarantine collisions fail safely.** Existing quarantined files are not overwritten.
- **A failed quarantine move retains the source directory.** The extension no longer removes a directory after an unsuccessful move.
- **Protected descendants now protect their parent candidate directory.** For example, `Sample/keep.srt` survives when `*.srt` is protected.
- **Relative Size % = 0 now disables relative detection** as documented. Absolute thresholds still apply when enabled.
- **Block Import now preserves the complete Test Mode preview for enabled removal types.** Individual `[TEST] Would remove...` lines and the normal candidate summary are printed before exit code 94 is returned.

### Clarified

- Documented the canonical category order: **Completion → PasswordDetector → ExtendedUnpacker → RemoveSamples → Clean**.
- Added a plain warning that Test Mode=No plus Quarantine Mode=No means permanent live deletion.
- Clarified that Test Mode makes no moves, Quarantine Mode is ignored during Test Mode, and Quarantine Max Age applies only to active live quarantine runs.
- Changed the summary threshold label from misleading `VideoMB>=` text to `VideoMaxMB` and separated file and directory candidate counts.

### Validation evidence for the deployed safety-fixed base

- 15/15 Python regression tests passed for the deployed safety-fixed base.
- Added regression coverage for every fixed safety case above.
- `ruff check main.py tests.py tools/unraid_smoke_test_v1111.py` passed.
- `manifest.json` validation and Python AST parsing passed.
- automated analysis graph rebuild and health checks passed.
- Bandit reported no medium- or high-severity findings; two existing low-severity broad-exception findings remain for later hardening.
- The target NZBGet Docker container completed the disposable staging harness with **7/7 checks passed** against the staged v1.1.1 `main.py`.
- The active `/config/scripts/RemoveSamples` deployment was hash-verified in the target container, its manifest parsed successfully, and it reported version **1.1.1**.
- A real overnight TV download completed successfully after ExtendedUnpacker, and the deployed base removed its explicit `Sample` directory in LIVE mode without a visible error.

### Revised clarity candidate validation

- 16/16 Python regression tests passed.
- The final local disposable integration harness passed **8/8**, including ordered Block Import preview output before exit code 94.
- Ruff, manifest JSON validation, Python compilation, Git diff checks, and the automated analysis update passed.
- A controlled real NZBGet Test Mode run detected one 0.5 MB sample video and its `Sample` directory, reported `FileCandidates=1 DirCandidates=1`, and logged zero removals. NZBGet labeled the exit-95 result `skipped`, which is expected when Test Mode performs no destructive work. Sonarr subsequently removed the completed release through download-client cleanup; the user did not manually delete the History entry. Official Sonarr documentation confirms that `Remove Completed` can remove leftover files after import, and that `Remove Failed` can clear downloaded files after a failure. Because Block Import reports exit code 94, it prevents import but does not guarantee folder preservation when `Remove Failed` is enabled.
- A second controlled real run used Test Mode with Block Import enabled and Sonarr `Remove Failed` temporarily disabled. A FERENGI release containing a nested `Sample` directory triggered exit code 94 and the expected NZBGet `PP-FAILURE`; Sonarr did not import it, while the completed folder, approximately 1.7 GB main video, nested `Sample` directory, and approximately 23 MB sample video remained available for inspection. This confirms Block Import behavior and Test Mode non-deletion under the documented media-manager configuration.
- The same retained FERENGI release was then selected with NZBGet `Post-Process Again` under `Test Mode=No`, `Block Import=No`, `Quarantine Mode=Yes`, and zero-day automatic purge. RemoveSamples logged `[QUARANTINE] Directory contents moved`, reported `removed 0 files / 1 dirs`, `FileCandidates=1`, `DirCandidates=1`, `Mode: LIVE+QUARANTINE`, and completed successfully. NZBGet History changed from `PP-FAILURE` to `SUCCESS`; screenshots confirmed the approximately 23 MB sample under `_samples_quarantine/.../Sample/` while the separate main release folder remained. This completes the controlled real-world Quarantine observation.

### Release publication checklist

- [x] Revised local validation passed: **16/16** regression tests, **8/8** disposable integration checks, Ruff, manifest JSON, Python compile, and diff checks.
- [x] Final target-container disposable harness passed **8/8** with the Block Import preview refinement.
- [x] The earlier clarity candidate's active deployment hash and manifest version were verified in the target container.
- [x] Final `main.py`, `manifest.json`, and 8-check harness hashes were verified in staging and the active host deployment.
- [x] Final active-container hashes, manifest JSON, and Python syntax were verified read-only.
- [x] Final Git diff reviewed with no safety blocker or accidental artifacts.


The disposable harness creates and alters files only under `/data/usenet/complete/_temp_removesamples_v1111_smoke`, refuses to reuse that root, and preserves it for inspection. See `tools/unraid_smoke_test_v1111.py` for the generated fixtures and assertions.

### Upgrade notes

- The final reviewed v1.1.1 runtime is installed at `/config/scripts/RemoveSamples` and passed active-container hash, manifest JSON, version, and Python syntax verification.
- First use **Test Mode=Yes** with **Quarantine Mode=No** to review candidates without moving or deleting files.
- After reviewing Test Mode results, set **Test Mode=No**, then enable **Quarantine Mode=Yes** for the first controlled live-action run.
- Enable **Block Import (Test Mode)** only for a specific test when you accept that the release may be reported failed or blacklisted; turn it off afterward.
- Do not use the `incomplete` directory for post-processing validation; NZBGet post-processing operates on completed download paths.

## Verification basis

- Local code review and isolated temporary-directory probes
- Automated Python regression suite
- automated analysis AST relationship map
- NZBGet v23+ manifest contract validation
- Target LinuxServer NZBGet container staging validation and active deployment hash/manifest verification
