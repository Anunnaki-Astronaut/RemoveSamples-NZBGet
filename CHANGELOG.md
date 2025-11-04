# Changelog

## v1.1.0

This release introduces several powerful new features for more flexible and safer sample detection, along with a new Test Mode for previewing changes.

### New Features
*   **Test Mode**: A new safe-run option that logs what the script *would* remove without changing any files. Perfect for tuning settings.
*   **Block Import During Test**: An optional companion to Test Mode that tells NZBGet to report a failure, preventing media managers from importing a download during a test run.
*   **Relative Size % Detection**: A new detection method that identifies a video file as a sample if its size is below a certain percentage of the largest video in the same download. This allows for dynamic thresholds based on the content (e.g., 8% of a 10 GB movie vs. 8% of a 2 GB TV episode).
*   **Category Thresholds**: Users can now override the global Relative Size % for specific NZBGet categories.
*   **Protected Names/Paths**: A new option to specify file and directory names/patterns that should *never* be removed, giving users full control to protect important assets like subtitles or posters.
*   **Deny Patterns**: An extra list of user-defined patterns to flag additional files for removal.
*   **Image Samples & Junk Extras**: Optional toggles to remove common image-based samples and other release clutter like `.url` files.
*   **Quarantine Mode**: Instead of permanently deleting files, this mode moves them to a `_samples_quarantine` subfolder for review.
*   **Quarantine Max Age**: An automatic purge option to delete files from the quarantine folder after a specified number of days.

### Notes
*   Change history for versions prior to v1.1.0 can be found in the release tags on GitHub.