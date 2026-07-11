#!/usr/bin/env python3
"""Disposable integration checks for RemoveSamples v1.1.1 on NZBGet/Unraid.

The harness only creates and alters files inside a directory named
``_ka_removesamples_v1111_smoke``. It refuses to reuse an existing root so
prior evidence cannot be overwritten accidentally.
"""

import argparse
import os
import subprocess  # nosec B404
import sys
import time
from pathlib import Path
from typing import Dict, Tuple

POSTPROCESS_SUCCESS = 93
POSTPROCESS_ERROR = 94
POSTPROCESS_NONE = 95
ROOT_NAME = "_ka_removesamples_v1111_smoke"
DEFAULT_ROOT = Path("/data/usenet/complete") / ROOT_NAME
DEFAULT_SCRIPT = Path(__file__).resolve().parents[1] / "main.py"


def build_environment(destination: Path, updates: Dict[str, str]) -> Dict[str, str]:
    """Build a complete deterministic NZBGet post-processing environment."""
    env = os.environ.copy()
    env.update(
        {
            "NZBPP_DIRECTORY": str(destination),
            "NZBPP_STATUS": "SUCCESS",
            "NZBPP_NZBNAME": "RemoveSamples-v1.1.1-smoke",
            "NZBPO_REMOVEDIRECTORIES": "Yes",
            "NZBPO_REMOVEFILES": "Yes",
            "NZBPO_DEBUG": "Yes",
            "NZBPO_VIDEOSIZETHRESHOLDMB": "150",
            "NZBPO_VIDEOEXTS": ".mkv,.mp4,.avi,.mov,.wmv,.flv,.webm,.ts,.m4v,.vob,.mpg,.mpeg,.iso",
            "NZBPO_AUDIOSIZETHRESHOLDMB": "2",
            "NZBPO_AUDIOEXTS": ".mp3,.flac,.aac,.ogg,.wma,.m4a,.opus,.wav,.alac,.ape",
            "NZBPO_TESTMODE": "No",
            "NZBPO_BLOCKIMPORTDURINGTEST": "No",
            "NZBPO_RELATIVEPERCENT": "8",
            "NZBPO_PROTECTEDPATHS": "",
            "NZBPO_DENYPATTERNS": "",
            "NZBPO_IMAGESAMPLES": "No",
            "NZBPO_JUNKEXTRAS": "No",
            "NZBPO_CATEGORYTHRESHOLDS": "",
            "NZBPO_QUARANTINEMODE": "No",
            "NZBPO_QUARANTINEMAXAGEDAYS": "0",
        }
    )
    env.update(updates)
    return env


def run_script(script: Path, destination: Path, updates: Dict[str, str]) -> Tuple[int, str, str]:
    """Run the extension and return its NZBGet exit code and captured logs."""
    completed = subprocess.run(
        [sys.executable, str(script)],  # nosec B603
        env=build_environment(destination, updates),
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode, completed.stdout, completed.stderr


def sparse_file(path: Path, size: int) -> None:
    """Create a sparse placeholder with the requested apparent size."""
    with path.open("wb") as handle:
        handle.seek(size - 1)
        handle.write(b"\0")


def execute_case(
    label: str,
    script: Path,
    case_dir: Path,
    updates: Dict[str, str],
    expected_code: int,
    verify,
    expected_output: Tuple[str, ...] = (),
) -> bool:
    code, stdout, stderr = run_script(script, case_dir, updates)
    passed = code == expected_code
    if passed:
        try:
            verify()
            cursor = -1
            for marker in expected_output:
                cursor = stdout.find(marker, cursor + 1)
                if cursor < 0:
                    raise AssertionError(f"missing or out-of-order output: {marker}")
        except AssertionError as exc:
            passed = False
            print(f"VERIFY FAILURE: {exc}")

    status = "PASS" if passed else "FAIL"
    print(f"\n[{status}] {label}: expected exit={expected_code}, got exit={code}")
    print("--- extension stdout ---")
    print(stdout.rstrip() or "(empty)")
    if stderr:
        print("--- extension stderr ---")
        print(stderr.rstrip())
    return passed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help=f"Disposable test root (default: {DEFAULT_ROOT})",
    )
    parser.add_argument(
        "--script",
        type=Path,
        default=DEFAULT_SCRIPT,
        help=f"RemoveSamples main.py path (default: {DEFAULT_SCRIPT})",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    script = args.script.resolve()
    if root.name != ROOT_NAME:
        parser.error(f"--root must end with {ROOT_NAME!r}; refusing unsafe location: {root}")
    if root.exists():
        parser.error(f"refusing to reuse existing test root: {root}")
    if not script.is_file():
        parser.error(f"main.py not found: {script}")

    root.mkdir(parents=True)
    print(f"Created disposable test root: {root}")
    print(f"Using extension script: {script}")
    print("The harness preserves all results for inspection; delete the root manually when finished.")

    passed = []

    test_mode_dir = root / "01-test-mode-quarantine"
    quarantine_dir = test_mode_dir / "_samples_quarantine"
    quarantine_dir.mkdir(parents=True)
    old_file = quarantine_dir / "old.txt"
    old_file.write_text("must survive test mode", encoding="utf-8")
    old_time = time.time() - (10 * 86400)
    os.utime(old_file, (old_time, old_time))
    passed.append(
        execute_case(
            "Test Mode does not purge old quarantine content",
            script,
            test_mode_dir,
            {
                "NZBPO_TESTMODE": "Yes",
                "NZBPO_QUARANTINEMODE": "Yes",
                "NZBPO_QUARANTINEMAXAGEDAYS": "7",
                "NZBPO_REMOVEFILES": "No",
                "NZBPO_REMOVEDIRECTORIES": "No",
            },
            POSTPROCESS_NONE,
            lambda: (_ for _ in ()).throw(AssertionError("old quarantine file was removed"))
            if not old_file.exists()
            else None,
        )
    )

    existing_dir = root / "02-existing-quarantine"
    old_quarantine_file = existing_dir / "_samples_quarantine" / "old.sample.mkv"
    old_quarantine_file.parent.mkdir(parents=True)
    old_quarantine_file.write_bytes(b"existing quarantine content")
    passed.append(
        execute_case(
            "Existing quarantine is not reprocessed",
            script,
            existing_dir,
            {"NZBPO_QUARANTINEMODE": "Yes"},
            POSTPROCESS_NONE,
            lambda: (_ for _ in ()).throw(AssertionError("existing quarantine content was removed"))
            if not old_quarantine_file.exists()
            else None,
        )
    )

    protected_dir = root / "03-protected-descendant"
    protected_file = protected_dir / "Sample" / "keep.srt"
    protected_file.parent.mkdir(parents=True)
    protected_file.write_text("protected subtitle", encoding="utf-8")
    passed.append(
        execute_case(
            "Protected descendant blocks sample-directory removal",
            script,
            protected_dir,
            {"NZBPO_PROTECTEDPATHS": "*.srt"},
            POSTPROCESS_NONE,
            lambda: (_ for _ in ()).throw(AssertionError("protected file or its parent was removed"))
            if not protected_file.exists() or not protected_file.parent.exists()
            else None,
        )
    )

    relative_dir = root / "04-relative-percent-zero"
    relative_dir.mkdir()
    tiny_video = relative_dir / "tiny.mkv"
    tiny_video.write_bytes(b"x")
    large_video = relative_dir / "feature.mkv"
    sparse_file(large_video, 1024 * 1024)
    passed.append(
        execute_case(
            "RelativePercent=0 disables relative detection",
            script,
            relative_dir,
            {"NZBPO_VIDEOSIZETHRESHOLDMB": "0", "NZBPO_RELATIVEPERCENT": "0"},
            POSTPROCESS_NONE,
            lambda: (_ for _ in ()).throw(AssertionError("video was selected while relative detection was disabled"))
            if not tiny_video.exists() or not large_video.exists()
            else None,
        )
    )

    collision_dir = root / "05-quarantine-collision"
    source_file = collision_dir / "Sample" / "keep.txt"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("source", encoding="utf-8")
    existing_copy = collision_dir / "_samples_quarantine" / "Sample" / "keep.txt"
    existing_copy.parent.mkdir(parents=True)
    existing_copy.write_text("existing", encoding="utf-8")

    def verify_collision() -> None:
        if source_file.read_text(encoding="utf-8") != "source":
            raise AssertionError("source was overwritten or removed")
        if existing_copy.read_text(encoding="utf-8") != "existing":
            raise AssertionError("quarantine copy was overwritten")

    passed.append(
        execute_case(
            "Quarantine collision retains source and prior quarantine copy",
            script,
            collision_dir,
            {"NZBPO_QUARANTINEMODE": "Yes"},
            POSTPROCESS_ERROR,
            verify_collision,
        )
    )

    live_quarantine_dir = root / "06-live-quarantine"
    quarantined_source = live_quarantine_dir / "Sample" / "demo.txt"
    quarantined_source.parent.mkdir(parents=True)
    quarantined_source.write_text("move me", encoding="utf-8")
    quarantined_copy = live_quarantine_dir / "_samples_quarantine" / "Sample" / "demo.txt"

    def verify_live_quarantine() -> None:
        if quarantined_source.exists():
            raise AssertionError("source remained after a successful quarantine move")
        if quarantined_copy.read_text(encoding="utf-8") != "move me":
            raise AssertionError("quarantine copy is missing or changed")

    passed.append(
        execute_case(
            "Live quarantine moves only disposable sample content",
            script,
            live_quarantine_dir,
            {"NZBPO_QUARANTINEMODE": "Yes"},
            POSTPROCESS_SUCCESS,
            verify_live_quarantine,
        )
    )

    direct_delete_dir = root / "07-live-delete"
    delete_source = direct_delete_dir / "Sample" / "delete-me.txt"
    delete_source.parent.mkdir(parents=True)
    delete_source.write_text("disposable", encoding="utf-8")
    passed.append(
        execute_case(
            "Live deletion affects only disposable test content",
            script,
            direct_delete_dir,
            {},
            POSTPROCESS_SUCCESS,
            lambda: (_ for _ in ()).throw(AssertionError("disposable sample directory was not removed"))
            if delete_source.parent.exists()
            else None,
        )
    )

    block_import_dir = root / "08-block-import-preview"
    block_import_file = block_import_dir / "Sample" / "sample-episode.mkv"
    block_import_file.parent.mkdir(parents=True)
    block_import_file.write_bytes(b"x" * 1024)
    passed.append(
        execute_case(
            "Block Import preserves the complete ordered Test Mode preview",
            script,
            block_import_dir,
            {
                "NZBPO_TESTMODE": "Yes",
                "NZBPO_BLOCKIMPORTDURINGTEST": "Yes",
            },
            POSTPROCESS_ERROR,
            lambda: (_ for _ in ()).throw(AssertionError("Test Mode changed the sample file"))
            if not block_import_file.exists()
            else None,
            (
                "[TEST] Would remove directory: Sample",
                "[TEST] Would remove file: Sample/sample-episode.mkv",
                "Summary: removed 0 files / 0 dirs",
                "FileCandidates=1 DirCandidates=1",
                "BlockImportDuringTest=ON with candidates → preview complete",
            ),
        )
    )

    failures = len([result for result in passed if not result])
    print(f"\nResult: {len(passed) - failures}/{len(passed)} checks passed.")
    print(f"Inspect or remove the disposable root manually: {root}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
