#!/usr/bin/env python3
#
# Tests for RemoveSamples Extension (v1.1.0 semantics)
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
        ".mkv,.mp4,.avi,.mov,.wmv,.flv,.webm,.ts,.m4v,.vob"
    )
    os.environ["NZBPO_AUDIOSIZETHRESHOLDMB"] = "2"
    os.environ["NZBPO_AUDIOEXTS"] = (
        ".wav,.aiff,.mp3,.flac,.m4a,.ogg,.aac,.alac,.ape,.opus,.wma"
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
        # v1.1.0 uses a summary line instead of "completed successfully"
        self.assertIn("Summary: removed 0 files / 0 dirs", output)

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


if __name__ == "__main__":
    unittest.main()
