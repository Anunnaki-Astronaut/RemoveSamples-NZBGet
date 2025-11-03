#!/usr/bin/env python3
"""RemoveSamples NZBGet Extension.

Detects and deletes "sample" files and/or directories in a download
before Sonarr / Radarr / Lidarr / Prowlarr see them.
"""
##############################################################################
# Title : RemoveSamples.py
# Author: Anunnaki-Astronaut
# URL   : https://github.com/Anunnaki-Astronaut/RemoveSamples-NZBGet
##############################################################################
# NZBGET POST-PROCESSING SCRIPT
#
# Detects and deletes "sample" files and/or directories in a download
# before Sonarr / Radarr / Lidarr / Prowlarr see them.
#
# 1. In NZBGet ► Settings ► CATEGORIES select "RemoveSamples" in
#    "ExtensionScripts" for every category you want cleaned.
# 2. Script order: place RemoveSamples carefully within your workflow for
#    optimal results.
#
# NOTE: This script requires Python to be installed in the container/host.
#
##############################################################################

import os
import re
import shutil
import sys
import fnmatch
import time
from pathlib import Path

# === BEGIN_NZBGET_V23_CONTRACT ===
# Exit constants (DO NOT RENAME OR CHANGE VALUES)
POSTPROCESS_SUCCESS = 93
POSTPROCESS_ERROR = 94
POSTPROCESS_NONE = 95
# Required NZBGet envs
# - NZBPP_DIRECTORY
# - NZBPP_STATUS (fallback to NZBPP_TOTALSTATUS)
# - NZBPP_NZBNAME (optional)
#
# Required options for v1.0.3+
# - NZBPO_REMOVEDIRECTORIES
# - NZBPO_REMOVEFILES
# - NZBPO_DEBUG
# - NZBPO_VIDEOSIZETHRESHOLDMB
# - NZBPO_VIDEOEXTS
# - NZBPO_AUDIOSIZETHRESHOLDMB
# - NZBPO_AUDIOEXTS
#
# Allowed optional options (v1.1.0+)
# - NZBPO_TESTMODE
# - NZBPO_BLOCKIMPORTDURINGTEST
# - NZBPO_RELATIVEPERCENT
# - NZBPO_PROTECTEDPATHS
# - NZBPO_DENYPATTERNS
# - NZBPO_IMAGESAMPLES
# - NZBPO_JUNKEXTRAS
# - NZBPO_CATEGORYTHRESHOLDS
# - NZBPO_QUARANTINEMODE
# - NZBPO_QUARANTINEMAXAGEDAYS
# === END_NZBGET_V23_CONTRACT ===


# Force UTF-8 console on Windows to avoid UnicodeEncodeError in debug logs
def _enable_utf8_windows():
    if os.name == "nt":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass  # Continue silently if UTF-8 can't be forced


_enable_utf8_windows()


# ---------- Helpers ----------
def _env_bool(key, default=False):
    val = os.environ.get(key)
    if val is None:
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "on", "y", "t", "enabled", "enable")


def _env_int(key, default=0):
    try:
        return int(str(os.environ.get(key, str(default))).strip())
    except (ValueError, TypeError):
        return default


def _env_str(key, default=""):
    return str(os.environ.get(key, default)).strip()


def _parse_exts(s):
    if not s:
        return set()
    out = set()
    for t in re.split(r"[,\s;]+", s):
        t = t.strip().lower()
        if not t:
            continue
        if not t.startswith("."):
            t = "." + t
        out.add(t)
    return out


def _csv_list(s):
    if not s:
        return []
    return [x.strip() for x in re.split(r"[,;\n]+", s) if x.strip()]


def info(msg): print(f"[INFO] {msg}", flush=True)
def error(msg): print(f"[ERROR] {msg}", flush=True)
def debug_enabled(): return _env_bool("NZBPO_DEBUG", False)
def debug(msg):
    if debug_enabled():
        print(f"[DEBUG] {msg}", flush=True)


def _size_mb(p: Path) -> float:
    try:
        return p.stat().st_size / (1024 * 1024)
    except OSError:
        return 0.0


def _matches_any(base: Path, p: Path, patterns):
    if not patterns:
        return False
    # Use resolved paths for accurate relative_to checks
    try:
        rel = str(p.resolve().relative_to(base.resolve())).replace("\\", "/")
    except ValueError:
        rel = str(p.resolve()).replace("\\", "/") # Fallback if not relative
    name = p.name
    for pat in patterns:
        if fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(rel, pat):
            return True
    return False


def _parse_cat_overrides(s: str):
    out = {}
    for part in [t.strip() for t in s.split(",") if t.strip()]:
        if "=" in part:
            k, v = part.split("=", 1)
            try:
                out[k.strip().lower()] = int(v.strip())
            except ValueError:
                pass
    return out


print("[DETAIL] RemoveSamples extension started")
sys.stdout.flush()

# Check required options from v1.0.3
REQUIRED_OPTIONS = (
    "NZBPO_REMOVEDIRECTORIES",
    "NZBPO_REMOVEFILES",
    "NZBPO_DEBUG",
    "NZBPO_VIDEOSIZETHRESHOLDMB",
    "NZBPO_VIDEOEXTS",
    "NZBPO_AUDIOSIZETHRESHOLDMB",
    "NZBPO_AUDIOEXTS"
)

for optname in REQUIRED_OPTIONS:
    if optname not in os.environ:
        error_msg = (
            f"Option {optname[6:]} is missing in configuration "
            f"file. Please check script settings"
        )
        error(error_msg)
        sys.exit(POSTPROCESS_ERROR)


# ---------- Inputs ----------
DL_STATUS = os.environ.get("NZBPP_STATUS", "") or os.environ.get("NZBPP_TOTALSTATUS", "")
DEST_DIR = Path(_env_str("NZBPP_DIRECTORY", ".")).resolve()
NZB_NAME = _env_str("NZBPP_NZBNAME", "")
CATEGORY = _env_str("NZBPP_CATEGORY", "")

# v1.0.3 options
REMOVE_DIRS = _env_bool("NZBPO_REMOVEDIRECTORIES", False)
REMOVE_FILES = _env_bool("NZBPO_REMOVEFILES", False)
VID_LIMIT = _env_int("NZBPO_VIDEOSIZETHRESHOLDMB", 150)
AUD_LIMIT = _env_int("NZBPO_AUDIOSIZETHRESHOLDMB", 2)
VIDEO_EXTS = _parse_exts(_env_str("NZBPO_VIDEOEXTS", ".mkv,.mp4,.avi,.mov,.ts,.m4v,.wmv"))
AUDIO_EXTS = _parse_exts(_env_str("NZBPO_AUDIOEXTS", ".mp3,.flac,.aac,.m4a,.ogg,.opus,.wav"))

# v1.1.0 optional features
TEST_MODE = _env_bool("NZBPO_TESTMODE", False)
BLOCK_IMPORT_DURING_TEST = _env_bool("NZBPO_BLOCKIMPORTDURINGTEST", False)
RELATIVE_PERCENT = _env_int("NZBPO_RELATIVEPERCENT", -1)
PROTECTED_PATHS = _csv_list(_env_str("NZBPO_PROTECTEDPATHS", ""))
DENY_PATTERNS = _csv_list(_env_str("NZBPO_DENYPATTERNS", ""))
IMAGE_SAMPLES = _env_bool("NZBPO_IMAGESAMPLES", False)
JUNK_EXTRAS = _env_bool("NZBPO_JUNKEXTRAS", False)
CATEGORY_THRESH = _env_str("NZBPO_CATEGORYTHRESHOLDS", "")
QUARANTINE_MODE = _env_bool("NZBPO_QUARANTINEMODE", False)
QUARANTINE_MAX_AGE_DAYS = _env_int("NZBPO_QUARANTINEMAXAGEDAYS", 0)

# Name patterns for "sample"
SAMPLE_NAME_RE_FILE = re.compile(r"(?i)(?:^|[\\/_\.\-\s])sample(?:s)?(?:$|[\\/_\.\-\s])")
SAMPLE_NAME_RE_DIR = re.compile(r"(?i)(?:^|[\\/_\.\-\s])samples?(?:$|[\\/_\.\-\s])")


def main():
    """Main entry point for the RemoveSamples extension."""
    if not _env_str("NZBPP_DIRECTORY"):
        error("NZBPP_DIRECTORY missing - script must run in post-processing mode")
        sys.exit(POSTPROCESS_ERROR)

    if not DL_STATUS.upper().startswith('SUCCESS'):
        info(f"Status {DL_STATUS}; skipping.")
        info("Summary: 0 removed (status not SUCCESS). Mode: " + ("TEST" if TEST_MODE else "LIVE"))
        sys.exit(POSTPROCESS_NONE)

    if not DEST_DIR.exists():
        error(f"Destination directory not found: {DEST_DIR}")
        sys.exit(POSTPROCESS_NONE)

    info(f'Processing "{NZB_NAME}" in {DEST_DIR}')

    # Category override for relative percent
    eff_relative_percent = RELATIVE_PERCENT
    cat_map = _parse_cat_overrides(CATEGORY_THRESH)
    if CATEGORY and cat_map and CATEGORY.lower() in cat_map:
        eff_relative_percent = cat_map[CATEGORY.lower()]
        info(f"Category override: {CATEGORY} → Relative Size % = {eff_relative_percent}")

    # Heads-up notes
    if TEST_MODE and QUARANTINE_MODE:
        info("Heads-up: Quarantine is ignored while Test Mode is ON.")
    if eff_relative_percent >= 0 and VID_LIMIT >= 400 and eff_relative_percent <= 5:
        info("Heads-up: High video threshold with low relative percent may skip everything.")
    if BLOCK_IMPORT_DURING_TEST and not TEST_MODE:
        info("Reminder: BlockImportDuringTest is designed for Test Mode.")

    # ---------- Scan ----------
    files_considered = 0
    dirs_considered = 0
    file_candidates = []
    dir_candidates = []
    errors = 0

    def is_video(p: Path) -> bool: return p.suffix.lower() in VIDEO_EXTS
    def is_audio(p: Path) -> bool: return p.suffix.lower() in AUDIO_EXTS
    def is_image(p: Path) -> bool: return p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}

    all_files = []
    all_dirs = []
    for p in DEST_DIR.rglob("*"):
        try:
            if p.is_symlink():
                debug(f"Skip symlink: {p}")
                continue
            if p.is_file():
                all_files.append(p)
            elif p.is_dir():
                all_dirs.append(p)
        except Exception as ex:
            errors += 1
            error(f"Scan error at {p}: {ex}")

    files_considered = len(all_files)
    dirs_considered = len(all_dirs)

    largest_video_bytes = 0
    if eff_relative_percent >= 0:
        for f in all_files:
            if is_video(f):
                try:
                    s = f.stat().st_size
                    if s > largest_video_bytes:
                        largest_video_bytes = s
                except OSError:
                    pass

    # Directories by name pattern
    for d in all_dirs:
        try:
            if SAMPLE_NAME_RE_DIR.search(d.name):
                if _matches_any(DEST_DIR, d, PROTECTED_PATHS):
                    debug(f"Protected directory: {d}")
                else:
                    dir_candidates.append(d)
                    debug(f"Candidate dir: {d}")
        except Exception as ex:
            errors += 1
            error(f"Dir scan error at {d}: {ex}")

    # Files by name, size, optional extras
    for f in all_files:
        try:
            if _matches_any(DEST_DIR, f, PROTECTED_PATHS):
                debug(f"Protected file: {f}")
                continue

            mb = _size_mb(f)
            name_hit = SAMPLE_NAME_RE_FILE.search(f.name) is not None
            small_video = is_video(f) and (VID_LIMIT > 0 and mb < float(VID_LIMIT))
            small_audio = is_audio(f) and (AUD_LIMIT > 0 and mb < float(AUD_LIMIT))

            rel_hit = False
            if is_video(f) and eff_relative_percent >= 0 and largest_video_bytes > 0:
                try:
                    pct = int(round((f.stat().st_size / largest_video_bytes) * 100))
                    rel_hit = (pct <= eff_relative_percent)
                except OSError:
                    rel_hit = False

            deny_hit = _matches_any(DEST_DIR, f, DENY_PATTERNS)
            image_hit = IMAGE_SAMPLES and is_image(f) and (("sample" in f.name.lower()) or deny_hit)
            junk_hit = JUNK_EXTRAS and (deny_hit or f.suffix.lower() in {".url", ".webloc"} or f.name.lower().endswith("readme.txt"))

            if name_hit or small_video or small_audio or rel_hit or image_hit or junk_hit or deny_hit:
                file_candidates.append((f, mb, name_hit, small_video, small_audio, rel_hit, image_hit, junk_hit, deny_hit))
                debug(f"Candidate file: {f} | {mb:.1f} MB | name={name_hit} smallV={small_video} smallA={small_audio} rel%={rel_hit} img={image_hit} junk={junk_hit} deny={deny_hit}")

        except Exception as ex:
            errors += 1
            error(f"File scan error at {f}: {ex}")

    if TEST_MODE and BLOCK_IMPORT_DURING_TEST and (file_candidates or dir_candidates):
        info("BlockImportDuringTest=ON with candidates → reporting 94 to prevent import (no deletions performed).")
        info("Summary: 0 removed (blocked during Test). Mode: TEST")
        sys.exit(POSTPROCESS_ERROR)

    # ---------- Act ----------
    removed_files = 0
    removed_dirs = 0
    removed_mb_total = 0.0
    quar_dir = DEST_DIR / "_samples_quarantine"

    def _safe_move(src: Path):
        dst = quar_dir / src.resolve().relative_to(DEST_DIR)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))

    # Directories
    if REMOVE_DIRS:
        for d in sorted(dir_candidates, key=lambda p: len(str(p)), reverse=True):
            try:
                rel = d.resolve().relative_to(DEST_DIR)
                if TEST_MODE:
                    info(f"[TEST] Would remove directory: {rel}")
                elif QUARANTINE_MODE:
                    moved_any = False
                    for p in d.rglob("*"):
                        if p.is_file():
                            try:
                                _safe_move(p)
                                moved_any = True
                            except Exception as ex:
                                errors += 1; error(f"Quarantine move failed {p}: {ex}")
                    shutil.rmtree(d, ignore_errors=True)
                    if moved_any: removed_dirs += 1; info(f"[QUARANTINE] Directory contents moved: {rel}")
                else:
                    shutil.rmtree(d)
                    removed_dirs += 1
                    info(f"Removed directory: {rel}")
            except Exception as ex:
                errors += 1; error(f"Failed to process directory: {d} - {ex}")
    else:
        debug("Configured to keep directories (NZBPO_REMOVEDIRECTORIES=No)")

    # Files
    if REMOVE_FILES:
        for f_tuple in file_candidates:
            f, mb, *_ = f_tuple
            try:
                # Re-check existence as parent dir might be gone
                if not f.exists():
                    continue
                rel = f.resolve().relative_to(DEST_DIR)
                if TEST_MODE:
                    info(f"[TEST] Would remove file: {rel} ({mb:.1f} MB)")
                elif QUARANTINE_MODE:
                    _safe_move(f)
                    removed_files += 1; removed_mb_total += mb
                    info(f"[QUARANTINE] {rel} ({mb:.1f} MB)")
                else:
                    f.unlink()
                    removed_files += 1; removed_mb_total += mb
                    info(f"Removed file: {rel} ({mb:.1f} MB)")
            except Exception as ex:
                errors += 1; error(f"Failed to process file: {f} - {ex}")
    else:
        debug("Configured to keep files (NZBPO_REMOVEFILES=No)")

    mode = "TEST" if TEST_MODE else ("LIVE+QUARANTINE" if QUARANTINE_MODE else "LIVE")
    info(
        f"Summary: removed {removed_files} files / {removed_dirs} dirs "
        f"({removed_mb_total:.1f} MB). Mode: {mode}. "
        f"FilesChecked={files_considered} DirsChecked={dirs_considered} "
        f"Candidates={len(file_candidates)+len(dir_candidates)} "
        f"Rel%={'disabled' if eff_relative_percent < 0 else eff_relative_percent} "
        f"VideoMB>={VID_LIMIT}"
    )

    if QUARANTINE_MODE and QUARANTINE_MAX_AGE_DAYS > 0 and quar_dir.exists():
        cutoff = time.time() - (QUARANTINE_MAX_AGE_DAYS * 86400)
        try:
            for p in quar_dir.rglob("*"):
                try:
                    if p.is_file() and p.stat().st_mtime < cutoff:
                        p.unlink(); debug(f"Purged old quarantine file: {p.name}")
                except Exception as ex:
                    error(f"Quarantine purge failed at {p}: {ex}")
            # Clean up empty subdirs
            for sub in sorted(quar_dir.rglob("*"), key=lambda p: len(str(p)), reverse=True):
                if sub.is_dir() and not any(sub.iterdir()):
                    sub.rmdir()
        except Exception:
            pass
    
    if errors > 0:
        sys.exit(POSTPROCESS_ERROR)
    
    if removed_files == 0 and removed_dirs == 0:
        # Exit 95 if no action was taken. In Test Mode, this is the expected outcome
        # if candidates were found but no removal occurred.
        sys.exit(POSTPROCESS_NONE)

    sys.exit(POSTPROCESS_SUCCESS)


if __name__ == '__main__':
    main()
