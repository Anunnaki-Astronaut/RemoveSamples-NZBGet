# Remove Samples • NZBGet Extension

[![Tests](https://github.com/Anunnaki-Astronaut/RemoveSamples-NZBGet/actions/workflows/tests.yml/badge.svg)](https://github.com/Anunnaki-Astronaut/RemoveSamples-NZBGet/actions/workflows/tests.yml)
[![Prospector](https://github.com/Anunnaki-Astronaut/RemoveSamples-NZBGet/actions/workflows/prospector.yml/badge.svg)](https://github.com/Anunnaki-Astronaut/RemoveSamples-NZBGet/actions/workflows/prospector.yml)
[![Manifest Check](https://github.com/Anunnaki-Astronaut/RemoveSamples-NZBGet/actions/workflows/manifest.yml/badge.svg)](https://github.com/Anunnaki-Astronaut/RemoveSamples-NZBGet/actions/workflows/manifest.yml)

NZBGet extension that removes "sample" files and folders before Sonarr/Radarr/Lidarr/Prowlarr see the download. Keeps your library clean while protecting real content with conservative defaults.

---

## Overview

Scene releases often include short sample clips, promo images, and other junk alongside the real media. If those make it into your library you get:

* noisy episode/movie folders
* extra files in Plex/Jellyfin/Kodi
* higher chance of grabbing the wrong file in manual imports

**Remove Samples** runs after unpacking and before your media managers. It identifies sample-like content using filename patterns, size thresholds, and optional relative-size rules, then removes (or quarantines) the junk so only real media moves downstream.

---

## Key features

* **Sample-aware filename matching**
  Detects common patterns like `sample`, `SAMPLE`, `.sample.`, `_sample_`, etc., using word- and separator-aware matching to avoid false positives.

* **Size-based detection for video & audio**
  Treats very small video and audio files under your thresholds as samples (e.g. tiny preview clips).

* **Relative Size % detection (optional)**
  Flags a video as a sample when its size is below a certain percentage of the largest video in the same download. This gives you dynamic thresholds that scale with the release.

* **Per-category overrides**
  Category-specific thresholds let you tune behavior differently for TV, movies, music, etc., while keeping safe global defaults.

* **Safety tools for testing and recovery**

  * **Test Mode** – dry-run logging that shows what *would* be removed without touching the files.
  * **Block Import During Test** – optional companion to Test Mode that tells NZBGet to report a failure so media managers don’t import during a test run.
  * **Quarantine Mode** – instead of deleting, moves samples to a `_samples_quarantine` subfolder for manual review.
  * **Quarantine Max Age** – optional automatic cleanup of old quarantine files after a configurable number of days.

* **Protected Paths & Deny Patterns**

  * **Protected paths/names** let you explicitly shield things like subtitles, artwork, or NFOs so they are never removed, even if they look like samples.
  * **Deny patterns** are a configurable list of extra patterns you always want treated as junk.

* **Image & extras cleanup (optional)**
  Optional toggles to remove common screenshot/image samples and other minor extras left behind by some releases.

---

## Install

**NZBGet → Settings → Extension Manager**

1. Find **Remove Samples** in the list.
2. Click the download/install icon.
3. Open **Settings → Categories** and add **RemoveSamples** after **ExtendedUnpacker** and before **Clean** in each category that should use it.
4. For the first controlled run, set **Test Mode = Yes** and review the result before allowing live deletion or quarantine.

---

## Basic configuration

**NZBGet → Settings → Extension Manager → Remove Samples**

For most users, the defaults are a safe starting point:

* **Video Size Threshold (MB):** `150`
  Video files below this size are considered candidates for sample detection when there is no explicit name match.
* **Audio Size Threshold (MB):** `2`
  Audio files below this size (for example, preview tracks) are considered sample candidates when there is no explicit name match.
* **Remove Directories:** `Yes`
  Removes entire folders that look like sample directories.
* **Remove Files:** `Yes`
  Removes individual files that match sample patterns.
* **Debug:** `No`
  Leave off for daily use. Turn on temporarily when tuning settings or diagnosing behavior.

### Recommended defaults & safety notes

* Start with the bundled defaults; they are intentionally conservative.
* **Live deletion warning:** When **Test Mode = No** and **Quarantine Mode = No**, matching files and directories are permanently deleted.
* **Relative Size %** defaults to **8%**, which provides a good balance for most content. Most users can leave this and **Category Thresholds** at their defaults.
* **Protected Paths** always win: if a file matches a protected pattern (for example `*.srt` for subtitles), it will **never** be removed, even if it also looks like a sample.
* When experimenting with new thresholds or patterns, enable **Test Mode** first so you can review log output before allowing deletions or quarantine moves.

---

## Extension order in NZBGet

**NZBGet → Settings → Categories → `<Your Category>`.Extensions**

Place **RemoveSamples** **after** unpacking and **before** any final cleanup or media managers.

**Example (working setup):**

1. **Completion** – Verifies download completeness before processing
2. **PasswordDetector** – Detects password-protected archives early
3. **ExtendedUnpacker** – Extracts nested zip/rar archives
4. **RemoveSamples** – Removes sample files/folders **after unpack**
5. **Clean** – Final tidy-up

Optional detection scripts such as **FakeDetector** can run before **ExtendedUnpacker** when installed.

**Why order matters**

* Remove Samples runs **after unpack**, so it can see real files.
* It runs **before Clean**, so samples are removed before final cleanup.
* Upstream detection scripts run first to catch bad releases early.
* A non-empty category Extensions list overrides the global Extensions list, so verify this order in every category that uses RemoveSamples.

---

## Quick test / first-run checklist

**Recommended first step – Test Mode only**

1. In Extension Manager, set **Test Mode = Yes**.
2. (Optional) Enable **Block Import (Test Mode) = Yes** if you want to prevent Sonarr/Radarr/Lidarr/Prowlarr from seeing the test download.
3. Process a known-good test download.
4. Open **NZBGet → Messages** and review the log lines:

   * size checks for video/audio
   * matches on filename patterns
   * summary line showing how many files/dirs would be removed or quarantined
5. Once you’re satisfied, set **Test Mode = No** (and **Block Import (Test Mode) = No** if you enabled it) to allow real removals or quarantine moves.

**When to use Debug**

* Turn **Debug = Yes** **by itself** (with Test Mode left at `No`) when you need deeper, per-item decision details to understand *why* something was or wasn’t treated as a sample.
* After troubleshooting, set **Debug = No** again for normal operation.

---

## Why your files may "disappear" after a Test Mode run (read this first)

A common point of confusion: after a Test Mode run, the sample folder is still on disk — but it may later vanish because a media manager removed the completed download after import. RemoveSamples did not delete it.

**How Test Mode actually behaves**

* Test Mode only logs what *would* be removed. It performs **no deletions and no moves**.
* The summary line reports `Mode: TEST` and `removed 0 files / 0 dirs`.
* NZBGet may display the post-process result as **"skipped"**. That label means the script exited with no destructive action (exit code 95). It does **not** mean the script failed to run. Confirm the run using the `Mode: TEST` summary line and the `[TEST] Would remove ...` entries.

**What can remove the files instead (it is not RemoveSamples in Test Mode)**

| Action / setting | Removes sample/media files? | Notes |
|---|---|---|
| RemoveSamples **Test Mode** | No | Logs only. Safe preview by design. |
| RemoveSamples **Live deletion** (Test Mode=No, Quarantine Mode=No) | Yes | Permanent. Intended behavior, clearly labeled in the UI. |
| RemoveSamples **Quarantine Mode** | Moves only | Sample is relocated to `_samples_quarantine`, not deleted. |
| **Sonarr/Radarr/Prowlarr "Remove Completed Downloads"** | **Yes, after import** | The media manager imports the episode, then asks NZBGet to delete the completed release (including any sample or quarantine folder). This is the usual cause of "my sample vanished." |
| `UnpackCleanupDisk` (Unpack page) | Only the `.rar`/`.r##` archives | Leave this **enabled**; it does not touch extracted video/samples. |
| `NzbCleanupDisk` | Only the source `.nzb` metadata file | Does not touch media. |
| `KeepHistory` | Only the history *record* after N days | Does not delete files on its own. |

**Why a manual download can still be removed**

If your media manager monitors the same NZBGet category you used (for example, Sonarr monitoring category `tv`), it will pick up a manually added download in that category, import it, and then remove the completed folder via "Remove Completed Downloads." The download does not have to come from Sonarr — the category match is what triggers it.

**Safe workflow for observing Test Mode or Quarantine results**

1. Run Test Mode and review **NZBGet → Messages**.
2. Choose the observation behavior deliberately:
   * **Block Import (Test Mode) = Yes** prevents Sonarr/Radarr import by reporting failure code 94, but it does **not** guarantee that the folder survives. If the manager's **Failed Download Handling → Remove Failed** option is enabled, it may remove the failed download and clear its files; it may also blocklist or replace the release.
   * To preserve the folder, use a category the media manager does not monitor, pause the media manager, or temporarily disable its **Remove Failed** cleanup.
   * Disabling only **Remove Completed** is not enough when Block Import is enabled, because the run is reported as failed rather than completed.
3. Inspect the completed-download folder (or `_samples_quarantine`) before any media-manager cleanup occurs.
4. Only switch to Live deletion or Quarantine Mode once the Test Mode preview matches your expectation.

---

## Detection logic (short)

* **Word-boundary matching:** uses patterns like `\bsample\b` to avoid false positives inside longer words.
* **Separator-aware:** catches `.sample.`, `_sample_`, `-sample-`, and similar separators in filenames.
* **Size checks:** very small video/audio files under your thresholds are considered sample candidates.
* **Relative-size checks (optional):** flags videos that are much smaller than the main video in the same download when Relative Size % is enabled.

---

## Windows debug console note

If you previously saw a Unicode/console encoding error with **Debug** enabled on Windows, update to the latest version via Extension Manager. The script now uses UTF-8 console output on Windows so Debug works normally.

---

## NZBGet versions / requirements

* **NZBGet:** v23+ recommended
* **Python:** 3.8+ (required)

---

## Support

* **Bug Reports**: [https://github.com/Anunnaki-Astronaut/RemoveSamples-NZBGet/issues](https://github.com/Anunnaki-Astronaut/RemoveSamples-NZBGet/issues)
* **Discussions**: [https://github.com/Anunnaki-Astronaut/RemoveSamples-NZBGet/discussions](https://github.com/Anunnaki-Astronaut/RemoveSamples-NZBGet/discussions)

---

## License

**GNU General Public License v2.0** – see the LICENSE file for details.