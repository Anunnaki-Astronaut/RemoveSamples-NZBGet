#!/usr/bin/env python3
#
# Tests for RemoveSamples Extension (v1.1.0 semantics)
#
# - Uses POSTPROCESS_SUCCESS (93) for runs that actually delete something
# - Uses POSTPROCESS_NONE    (95) for runs that do no destructive work
#

import os
import sys
import shutil
import tempfile
import subprocess
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


if __name__ == "__main__":
    unittest.main()
