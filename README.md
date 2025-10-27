# Remove Samples • NZBGet Extension

Removes “sample” files and sample folders **before** Sonarr/Radarr/Lidarr/Prowlarr process your downloads. Keeps your library clean with safe defaults.

## Install

**NZBGet → Settings → Extension Manager**

1. Find **Remove Samples** in the list.
2. Click the download/install icon.
3. That’s it.

## Configure

**NZBGet → Settings → Extension Manager → Remove Samples**

* **Defaults** have been tested and should work for most users.
* **Video size threshold:** **150 MB**
* **Audio size threshold:** **2 MB**
* **Remove Directories:** Yes
* **Remove Files:** Yes
* **Debug:** Leave **Off** under normal use. Turn **On only** during initial setup or when investigating an issue.

## Extensions order

**NZBGet → Settings → Categories → Category1.Extensions**
Put **RemoveSamples** **after** unpacking and **before** any final cleanup or media managers.

**Example (working setup):**

1. **Completion** – Verifies download completeness before processing
2. **PasswordDetector** – Detects password-protected archives early
3. **FakeDetector** – Flags fake/corrupted releases
4. **ExtendedUnpacker** – Extracts nested zip/rar archives
5. **RemoveSamples** – Removes sample files/folders **after unpack**
6. **Clean** – Final tidy-up

**Why order matters**

* Remove Samples runs **after unpack**, so it can see real files.
* It runs **before Clean**, so samples are removed before final cleanup.
* Upstream detection scripts run first to catch bad releases early.

## Quick test (optional)

Turn **Debug = Yes**, process a test download, and review the log lines showing size checks and pattern matches.
When you’re satisfied, set **Debug = No** for normal operation.

## Detection logic (short)

* **Word-boundary matching:** `\bsample\b` avoids false positives
* **Separator-aware:** catches `.sample.`, `_sample_`, `-sample-`, etc.
* **Size checks:** small video/audio files under your thresholds are considered samples

## Windows debug console note

If you previously saw a Unicode/console encoding error with **Debug** enabled on Windows, update to the latest version via Extension Manager. The script now uses UTF-8 console output on Windows so Debug works normally.

## NZBGet versions / requirements

* **NZBGet:** v23+ recommended
* **Python:** 3.8+ (required)

## Support

* **Bug Reports**: [GitHub Issues](https://github.com/Anunnaki-Astronaut/RemoveSamples-NZBGet/issues)
* **Discussions**: [GitHub Discussions](https://github.com/Anunnaki-Astronaut/RemoveSamples-NZBGet/discussions)

## License

**GNU General Public License v2.0** - see [LICENSE](LICENSE) file for details.