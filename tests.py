#!/usr/bin/env python3
#
# Tests for RemoveSamples Extension (v1.1.1 semantics)
#
# - Uses POSTPROCESS_SUCCESS (93) for runs that actually delete something
# - Uses POSTPROCESS_NONE    (95) for runs that do no destructive work
#

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

POSTPROCESS_SUCCESS = 93
POSTPROCESS_ERROR = 94
POSTPROCESS_NONE = 95

ROOT_DIR = Path(__file__).resolve().parent
SCRIPT_PATH = ROOT_DIR / "main.py"


def set_defaults(test_dir: str) -> None:
    """Set default NZBGet environment variables for tests."""
    # Core NZBGet runtime envs
    os.environ["NZBPP_DIRECTORY"] = test_dir
    os.environ["NZBPP_STATUS"] = "SUCCESS"
    os.environ["NZBPP_NZBNAME"] = "Test-NZB"

    # Required options (mirror manifest defaults)
    os.environ["NZBPO_REMOVEDIRECTORIES"] = "Yes"
    os.environ["NZBPO_REMOVEFILES"] = "Yes"
    os.environ["NZBPO_DEBUG"] = "No"
    os.environ["NZBPO_VIDEOSIZETHRESHOLDMB"] = "150"
    os.environ["NZBPO_VIDEOEXTS"] = (
        ".mkv,.mp4,.avi,.mov,.wmv,.flv,.webm,.ts,.m4v,.vob,.mpg,.mpeg,.iso"
    )
    os.environ["NZBPO_AUDIOSIZETHRESHOLDMB"] = "2"
    os.environ["NZBPO_AUDIOEXTS"] = (
        ".mp3,.flac,.aac,.ogg,.wma,.m4a,.opus,.wav,.alac,.ape"
    )

    # Optional toggles default off
    os.environ["NZBPO_TESTMODE"] = "No"
    os.environ["NZBPO_BLOCKIMPORTDURINGTEST"] = "No"
    os.environ["NZBPO_RELATIVEPERCENT"] = "8"
    os.environ["NZBPO_PROTECTEDPATHS"] = ""
    os.environ["NZBPO_DENYPATTERNS"] = ""
    os.environ["NZBPO_IMAGESAMPLES"] = "No"
    os.environ["NZBPO_JUNKEXTRAS"] = "No"
    os.environ["NZBPO_CATEGORYTHRESHOLDS"] = ""
    os.environ["NZBPO_QUARANTINEMODE"] = "No"
    os.environ["NZBPO_QUARANTINEMAXAGEDAYS"] = "0"


def run_script():
    """Run main.py as a subprocess and capture output and exit code."""
    proc = subprocess.Popen(
        [sys.executable, str(SCRIPT_PATH)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=os.environ.copy(),
    )
    out, err = proc.communicate()
    return out.decode("utf-8"), int(proc.returncode), err.decode("utf-8")


class TestRemoveSamples(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="rs_tests_")
        set_defaults(self.test_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # ---- Basic control-flow --------------------------------------------

    def test_script_success_no_work_done(self):
        """Empty dir with defaults should run and exit with POSTPROCESS_NONE."""
        output, code, error = run_script()
        self.assertEqual(code, POSTPROCESS_NONE)
        self.assertIn("RemoveSamples extension started", output)
        # v1.1.1 uses a concise, explicit summary line.
        self.assertIn("Summary: removed 0 files / 0 dirs", output)
        self.assertIn("FileCandidates=0 DirCandidates=0", output)
        self.assertIn("VideoMaxMB=150", output)
        self.assertNotIn("VideoMB>=", output)

    def test_missing_directory(self):
        """Missing NZBPP_DIRECTORY should be handled gracefully."""
        os.environ["NZBPP_DIRECTORY"] = "/nonexistent/directory"
        output, code, error = run_script()
        # Current behavior: treat as NONE and log an error line.
        self.assertEqual(code, POSTPROCESS_NONE)
        self.assertIn("Destination directory not found", output)

    def test_failed_status_skip(self):
        """If NZBPP_STATUS != SUCCESS, script should skip processing."""
        os.environ["NZBPP_STATUS"] = "FAILURE"
        output, code, error = run_script()
        self.assertEqual(code, POSTPROCESS_NONE)
        self.assertIn("skipping", output.lower())

    def test_block_import_logs_preview_and_summary_before_exit(self):
        """Block Import must preserve the complete Test Mode preview before exit 94."""
        os.environ["NZBPO_TESTMODE"] = "Yes"
        os.environ["NZBPO_BLOCKIMPORTDURINGTEST"] = "Yes"

        sample_dir = Path(self.test_dir) / "Sample"
        sample_dir.mkdir()
        sample_file = sample_dir / "sample-episode.mkv"
        sample_file.write_bytes(b"x" * 1024)

        output, code, error = run_script()

        self.assertEqual(code, POSTPROCESS_ERROR)
        self.assertTrue(sample_file.exists())
        self.assertIn("[TEST] Would remove directory: Sample", output)
        expected_file_log = f"[TEST] Would remove file: {Path('Sample') / 'sample-episode.mkv'}"
        self.assertIn(expected_file_log, output)
        self.assertIn("Summary: removed 0 files / 0 dirs", output)
        self.assertIn("FileCandidates=1 DirCandidates=1", output)
        block_message = "BlockImportDuringTest=ON with candidates"
        self.assertIn(block_message, output)
        self.assertLess(output.index("Summary:"), output.index(block_message))

    # ---- Sample detection ----------------------------------------------

    def test_sample_directory_detection(self):
        """Directories with 'sample' in the name should be removed."""
        sample_dir = Path(self.test_dir) / "Sample"
        sample_dir.mkdir()
        (sample_dir / "test.txt").write_text("content", encoding="utf-8")

        output, code, error = run_script()
        self.assertEqual(code, POSTPROCESS_SUCCESS)
        self.assertFalse(sample_dir.exists())

    def test_sample_file_detection(self):
        """Files with sample pattern in filename should be removed."""
        sample_file = Path(self.test_dir) / "movie.sample.mkv"
        sample_file.write_text("content", encoding="utf-8")

        output, code, error = run_script()
        self.assertEqual(code, POSTPROCESS_SUCCESS)
        self.assertFalse(sample_file.exists())

    def test_small_audio_file_detection(self):
        """Very small audio files under threshold should be treated as samples."""
        small_audio = Path(self.test_dir) / "track01.mp3"
        small_audio.write_bytes(b"x" * 1024)  # 1KB < 2MB threshold

        output, code, error = run_script()
        self.assertEqual(code, POSTPROCESS_SUCCESS)
        self.assertFalse(small_audio.exists())

    def test_small_video_file_detection(self):
        """Very small video files under threshold should be treated as samples."""
        small_video = Path(self.test_dir) / "movie.mkv"
        small_video.write_bytes(b"x" * 1024)  # 1KB < 150MB threshold

        output, code, error = run_script()
        self.assertEqual(code, POSTPROCESS_SUCCESS)
        self.assertFalse(small_video.exists())

    # ---- Non-sample and disabled behavior ------------------------------

    def test_normal_files_preserved(self):
        """Large non-sample videos should not be removed."""
        normal_file = Path(self.test_dir) / "movie.mkv"
        normal_file.write_bytes(b"x" * (200 * 1024 * 1024))  # 200MB > 150MB

        output, code, error = run_script()
        # Nothing removed -> NONE
        self.assertEqual(code, POSTPROCESS_NONE)
        self.assertTrue(normal_file.exists())

    def test_disabled_file_removal(self):
        """When REMOVEFILES is No, even obvious sample files are preserved."""
        os.environ["NZBPO_REMOVEFILES"] = "No"

        sample_file = Path(self.test_dir) / "movie.sample.mkv"
        sample_file.write_text("content", encoding="utf-8")

        output, code, error = run_script()
        self.assertEqual(code, POSTPROCESS_NONE)
        self.assertTrue(sample_file.exists())

    def test_disabled_directory_removal(self):
        """When REMOVEDIRECTORIES is No, sample directories are preserved."""
        os.environ["NZBPO_REMOVEDIRECTORIES"] = "No"

        sample_dir = Path(self.test_dir) / "Sample"
        sample_dir.mkdir()
        (sample_dir / "test.txt").write_text("content", encoding="utf-8")

        output, code, error = run_script()
        self.assertEqual(code, POSTPROCESS_NONE)
        self.assertTrue(sample_dir.exists())

    # ---- P0 safety regressions -----------------------------------------

    def test_test_mode_never_purges_quarantine(self):
        """Test Mode must not purge old quarantined files."""
        os.environ["NZBPO_TESTMODE"] = "Yes"
        os.environ["NZBPO_QUARANTINEMODE"] = "Yes"
        os.environ["NZBPO_QUARANTINEMAXAGEDAYS"] = "7"
        os.environ["NZBPO_REMOVEFILES"] = "No"
        os.environ["NZBPO_REMOVEDIRECTORIES"] = "No"

        quarantine_dir = Path(self.test_dir) / "_samples_quarantine"
        quarantine_dir.mkdir()
        old_file = quarantine_dir / "old.txt"
        old_file.write_text("must survive", encoding="utf-8")
        old_time = time.time() - (10 * 86400)
        os.utime(old_file, (old_time, old_time))

        output, code, error = run_script()
        self.assertEqual(code, POSTPROCESS_NONE)
        self.assertTrue(old_file.exists())
        self.assertIn("Mode: TEST", output)

    def test_existing_quarantine_is_not_reprocessed(self):
        """Existing quarantine content must survive another quarantine run."""
        os.environ["NZBPO_QUARANTINEMODE"] = "Yes"

        quarantine_dir = Path(self.test_dir) / "_samples_quarantine"
        quarantine_dir.mkdir()
        old_file = quarantine_dir / "old.sample.mkv"
        old_file.write_bytes(b"x")

        output, code, error = run_script()
        self.assertEqual(code, POSTPROCESS_NONE)
        self.assertTrue(quarantine_dir.exists())
        self.assertTrue(old_file.exists())

    def test_protected_descendant_blocks_sample_directory_removal(self):
        """Protected files inside a sample directory must prevent whole-dir removal."""
        os.environ["NZBPO_PROTECTEDPATHS"] = "*.srt"

        sample_dir = Path(self.test_dir) / "Sample"
        sample_dir.mkdir()
        protected_file = sample_dir / "keep.srt"
        protected_file.write_text("keep", encoding="utf-8")

        output, code, error = run_script()
        self.assertEqual(code, POSTPROCESS_NONE)
        self.assertTrue(sample_dir.exists())
        self.assertTrue(protected_file.exists())

    def test_relative_percent_zero_disables_relative_detection(self):
        """RelativePercent=0 must not select a tiny video by relative size."""
        os.environ["NZBPO_VIDEOSIZETHRESHOLDMB"] = "0"
        os.environ["NZBPO_RELATIVEPERCENT"] = "0"

        tiny_video = Path(self.test_dir) / "tiny.mkv"
        tiny_video.write_bytes(b"x")
        large_video = Path(self.test_dir) / "feature.mkv"
        with large_video.open("wb") as handle:
            handle.seek((1024 * 1024) - 1)
            handle.write(b"\0")

        output, code, error = run_script()
        self.assertEqual(code, POSTPROCESS_NONE)
        self.assertTrue(tiny_video.exists())
        self.assertTrue(large_video.exists())

    def test_quarantine_collision_keeps_source_and_existing_copy(self):
        """A quarantine collision must not overwrite or delete either file."""
        os.environ["NZBPO_QUARANTINEMODE"] = "Yes"

        sample_dir = Path(self.test_dir) / "Sample"
        sample_dir.mkdir()
        source_file = sample_dir / "keep.txt"
        source_file.write_text("source", encoding="utf-8")
        existing_copy = Path(self.test_dir) / "_samples_quarantine" / "Sample" / "keep.txt"
        existing_copy.parent.mkdir(parents=True)
        existing_copy.write_text("existing", encoding="utf-8")

        output, code, error = run_script()
        self.assertEqual(code, POSTPROCESS_ERROR)
        self.assertTrue(source_file.exists())
        self.assertEqual(source_file.read_text(encoding="utf-8"), "source")
        self.assertTrue(existing_copy.exists())
        self.assertEqual(existing_copy.read_text(encoding="utf-8"), "existing")

    def test_deny_pattern_does_not_select_directory(self):
        """DenyPatterns are file-only and must not authorize whole-directory action."""
        os.environ["NZBPO_DENYPATTERNS"] = "proof_dir"

        proof_dir = Path(self.test_dir) / "proof_dir"
        proof_dir.mkdir()
        proof_file = proof_dir / "content.bin"
        proof_file.write_bytes(b"content")

        output, code, error = run_script()
        self.assertEqual(code, POSTPROCESS_NONE)
        self.assertTrue(proof_dir.exists())
        self.assertTrue(proof_file.exists())

    @unittest.skipIf(os.name == "nt", "Symlink creation may require elevated Windows privileges")
    def test_symlinks_outside_dest_are_not_removed_or_followed(self):
        """Symlinks pointing outside the destination root must be ignored and not unlinked/followed."""
        os.environ["NZBPO_REMOVEFILES"] = "yes"
        os.environ["NZBPO_REMOVEDIRECTORIES"] = "yes"

        outside_dir = Path(tempfile.mkdtemp())
        try:
            target_file = outside_dir / "external_sample.mkv"
            target_file.write_bytes(b"0" * (10 * 1024 * 1024))

            link_file = Path(self.test_dir) / "sample.mkv"
            link_file.symlink_to(target_file)

            output, code, error = run_script()
            self.assertEqual(code, POSTPROCESS_ERROR)
            self.assertTrue(target_file.exists())
            self.assertTrue(link_file.is_symlink())
            self.assertIn("Unsafe path rejected", output)
        finally:
            shutil.rmtree(outside_dir, ignore_errors=True)

    def test_containment_helper_rejects_root_and_outside_paths(self):
        """The mutation containment guard accepts only existing descendants."""
        import importlib.util

        spec = importlib.util.spec_from_file_location("removesamples_test_module", SCRIPT_PATH)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        root = Path(self.test_dir)
        inside = root / "inside.bin"
        inside.write_bytes(b"content")
        outside_dir = Path(tempfile.mkdtemp())
        try:
            outside = outside_dir / "outside.bin"
            outside.write_bytes(b"content")
            self.assertTrue(module._is_contained_in_dest(inside, root))
            self.assertFalse(module._is_contained_in_dest(root, root))
            self.assertFalse(module._is_contained_in_dest(outside, root))
        finally:
            shutil.rmtree(outside_dir, ignore_errors=True)

    @unittest.skipIf(os.name == "nt", "Symlink creation may require elevated Windows privileges")
    def test_quarantine_retains_sample_directory_with_symlink(self):
        """Quarantine fails closed when a sample directory contains a link."""
        os.environ["NZBPO_QUARANTINEMODE"] = "Yes"
        sample_dir = Path(self.test_dir) / "Sample"
        sample_dir.mkdir()
        outside_dir = Path(tempfile.mkdtemp())
        try:
            target_file = outside_dir / "external.bin"
            target_file.write_bytes(b"external")
            link_file = sample_dir / "linked.bin"
            link_file.symlink_to(target_file)

            output, code, error = run_script()
            self.assertEqual(code, POSTPROCESS_ERROR)
            self.assertTrue(sample_dir.exists())
            self.assertTrue(link_file.is_symlink())
            self.assertEqual(target_file.read_bytes(), b"external")
        finally:
            shutil.rmtree(outside_dir, ignore_errors=True)

    @unittest.skipUnless(os.name == "nt", "Windows junction test")
    def test_windows_junction_is_rejected_without_touching_target(self):
        """A Windows junction inside a sample directory must never be traversed."""
        sample_dir = Path(self.test_dir) / "Sample"
        sample_dir.mkdir()
        outside_dir = Path(tempfile.mkdtemp())
        junction = sample_dir / "linked-folder"
        try:
            target_file = outside_dir / "important.bin"
            target_file.write_bytes(b"important")
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(junction), str(outside_dir)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))

            output, code, error = run_script()
            self.assertEqual(code, POSTPROCESS_ERROR)
            self.assertTrue(junction.exists())
            self.assertEqual(target_file.read_bytes(), b"important")
            self.assertIn("Windows reparse point", output)
        finally:
            if junction.exists():
                os.rmdir(str(junction))
            shutil.rmtree(outside_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
