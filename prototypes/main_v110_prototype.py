#!/usr/bin/env python3
"""
RemoveSamples NZBGet extension (v23+)
- Contract constants preserved
- Implements new optional features that match your manifest.json option names
"""

import os, re, sys, shutil, fnmatch, time
from pathlib import Path

# === BEGIN_NZBGET_V23_CONTRACT ===
# Exit constants (DO NOT RENAME OR CHANGE VALUES)
POSTPROCESS_SUCCESS = 93
POSTPROCESS_ERROR   = 94
POSTPROCESS_NONE    = 95

# Required NZBGet envs
# - NZBPP_DIRECTORY
# - NZBPP_STATUS (fallback to NZBPP_TOTALSTATUS)
# - NZBPP_NZBNAME (optional)
#
# Required options
# - NZBPO_REMOVEDIRECTORIES
# - NZBPO_REMOVEFILES
# - NZBPO_DEBUG
# - NZBPO_VIDEOSIZETHRESHOLDMB
# - NZBPO_VIDEOEXTS
# - NZBPO_AUDIOSIZETHRESHOLDMB
# - NZBPO_AUDIOEXTS
#
# Allowed optional options
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
            pass
_enable_utf8_windows()

# ---------- Helpers ----------
def _env_bool(key, default=False):
    val = os.environ.get(key)
    if val is None:
        return default
    return str(val).strip().lower() in ("1","true","yes","on","y","t","enabled","enable")

def _env_int(key, default=0):
    try:
        return int(str(os.environ.get(key, str(default))).strip())
    except Exception:
        return default

def _env_str(key, default=""):
    return str(os.environ.get(key, default)).strip()

def _parse_exts(s):
    if not s:
        return set()
    out = set()
    for t in re.split(r"[,\s;]+", s):
        if not t:
            continue
        t = t.lower()
        if not t.startswith("."):
            t = "." + t
        out.add(t)
    return out

def _csv_list(s):
    if not s:
        return []
    return [x.strip() for x in re.split(r"[,\n;]+", s) if x.strip()]

def info(msg):  print(f"[INFO] {msg}", flush=True)
def error(msg): print(f"[ERROR] {msg}", flush=True)
def debug_enabled(): return _env_bool("NZBPO_DEBUG", False)
def debug(msg):
    if debug_enabled():
        print(f"[DEBUG] {msg}", flush=True)

def _size_mb(p: Path) -> float:
    try:
        return p.stat().st_size / (1024 * 1024)
    except Exception:
        return 0.0

def _matches_any(base: Path, p: Path, patterns):
    if not patterns:
        return False
    rel = str(p.resolve().relative_to(base)).replace("\\", "/")
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
            except:
                pass
    return out

# ---------- Inputs ----------
DL_STATUS = os.environ.get("NZBPP_STATUS", "") or os.environ.get("NZBPP_TOTALSTATUS", "")
DEST_DIR  = Path(_env_str("NZBPP_DIRECTORY", ".")).resolve()
NZB_NAME  = _env_str("NZBPP_NZBNAME", "")
CATEGORY  = _env_str("NZBPP_CATEGORY", "")

REMOVE_DIRS = _env_bool("NZBPO_REMOVEDIRECTORIES", False)
REMOVE_FILES = _env_bool("NZBPO_REMOVEFILES", False)
VIDEO_MIN_MB = _env_int("NZBPO_VIDEOSIZETHRESHOLDMB", 200)
AUDIO_MIN_MB = _env_int("NZBPO_AUDIOSIZETHRESHOLDMB", 10)
VIDEO_EXTS = _parse_exts(_env_str("NZBPO_VIDEOEXTS", ".mkv,.mp4,.avi,.mov,.ts,.m4v,.wmv"))
AUDIO_EXTS = _parse_exts(_env_str("NZBPO_AUDIOEXTS", ".mp3,.flac,.aac,.m4a,.ogg,.opus,.wav"))

TEST_MODE = _env_bool("NZBPO_TESTMODE", False)
BLOCK_IMPORT_DURING_TEST = _env_bool("NZBPO_BLOCKIMPORTDURINGTEST", False)

# New optional features, mapped to your manifest option names
RELATIVE_PERCENT = _env_int("NZBPO_RELATIVEPERCENT", -1)  # -1 disables relative check
PROTECTED_PATHS  = _csv_list(_env_str("NZBPO_PROTECTEDPATHS", ""))
DENY_PATTERNS    = _csv_list(_env_str("NZBPO_DENYPATTERNS", ""))
IMAGE_SAMPLES    = _env_bool("NZBPO_IMAGESAMPLES", False)
JUNK_EXTRAS      = _env_bool("NZBPO_JUNKEXTRAS", False)
CATEGORY_THRESH  = _env_str("NZBPO_CATEGORYTHRESHOLDS", "")
QUARANTINE_MODE  = _env_bool("NZBPO_QUARANTINEMODE", False)
QUARANTINE_MAX_AGE_DAYS = _env_int("NZBPO_QUARANTINEMAXAGEDAYS", 0)

# Name patterns for "sample"
SAMPLE_NAME_RE_FILE = re.compile(r"(?i)(?:^|[\\/_\.\-\s])sample(?:s)?(?:$|[\\/_\.\-\s])")
SAMPLE_NAME_RE_DIR  = re.compile(r"(?i)(?:^|[\\/_\.\-\s])samples?(?:$|[\\/_\.\-\s])")

# ---------- Early sanity ----------
if not DEST_DIR.exists():
    error(f"Destination directory not found: {DEST_DIR}")
    sys.exit(POSTPROCESS_ERROR)

if DL_STATUS and DL_STATUS.upper() != "SUCCESS":
    info(f"Status {DL_STATUS}; skipping.")
    info("Summary: 0 removed (status not SUCCESS). Mode: " + ("TEST" if TEST_MODE else "LIVE"))
    sys.exit(POSTPROCESS_NONE)

info(f'Processing "{NZB_NAME}" in {DEST_DIR}')

# Category override for relative percent
EFF_RELATIVE_PERCENT = RELATIVE_PERCENT
cat_map = _parse_cat_overrides(CATEGORY_THRESH)
if CATEGORY and cat_map and CATEGORY.lower() in cat_map:
    EFF_RELATIVE_PERCENT = cat_map[CATEGORY.lower()]
    info(f"Category override: {CATEGORY} → Relative Size % = {EFF_RELATIVE_PERCENT}")

# Heads-up notes
if TEST_MODE and QUARANTINE_MODE:
    info("Heads-up: Quarantine is ignored while Test Mode is ON.")
if EFF_RELATIVE_PERCENT >= 0 and VIDEO_MIN_MB >= 400 and EFF_RELATIVE_PERCENT <= 5:
    info("Heads-up: Very high video threshold with very low relative percent may skip everything.")
if BLOCK_IMPORT_DURING_TEST and not TEST_MODE:
    info("Reminder: BlockImportDuringTest is designed for Test Mode.")

# ---------- Scan ----------
files_considered = 0
dirs_considered = 0
file_candidates = []
dir_candidates = []
errors = 0

def is_video(p: Path) -> bool:
    return p.suffix.lower() in VIDEO_EXTS

def is_audio(p: Path) -> bool:
    return p.suffix.lower() in AUDIO_EXTS

def is_image(p: Path) -> bool:
    return p.suffix.lower() in {".jpg",".jpeg",".png",".bmp",".gif",".webp"}

# Gather lists
all_files = []
all_dirs  = []
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

# Largest video size for relative percent logic
largest_video_bytes = 0
for f in all_files:
    if is_video(f):
        try:
            s = f.stat().st_size
            if s > largest_video_bytes:
                largest_video_bytes = s
        except Exception:
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
        small_video = is_video(f) and (mb < float(VIDEO_MIN_MB))
        small_audio = is_audio(f) and (mb < float(AUDIO_MIN_MB))

        rel_hit = False
        if is_video(f) and EFF_RELATIVE_PERCENT >= 0 and largest_video_bytes > 0:
            try:
                pct = int(round((f.stat().st_size / largest_video_bytes) * 100))
                rel_hit = (pct <= EFF_RELATIVE_PERCENT)
            except Exception:
                rel_hit = False

        deny_hit = _matches_any(DEST_DIR, f, DENY_PATTERNS)

        image_hit = False
        if IMAGE_SAMPLES and is_image(f):
            image_hit = ("sample" in f.name.lower()) or deny_hit

        junk_hit = False
        if JUNK_EXTRAS:
            junk_hit = deny_hit or f.suffix.lower() in {".url",".webloc"} or f.name.lower().endswith("readme.txt")

        if name_hit or small_video or small_audio or rel_hit or image_hit or junk_hit or deny_hit:
            file_candidates.append((f, mb, name_hit, small_video, small_audio, rel_hit, image_hit, junk_hit, deny_hit))
            debug(f"Candidate file: {f} | {mb:.1f} MB | name={name_hit} smallV={small_video} smallA={small_audio} rel%={rel_hit} img={image_hit} junk={junk_hit} deny={deny_hit}")

    except Exception as ex:
        errors += 1
        error(f"File scan error at {f}: {ex}")

# Optional block during test: return 94 early if candidates found
if TEST_MODE and BLOCK_IMPORT_DURING_TEST and (file_candidates or dir_candidates):
    info("BlockImportDuringTest=ON with candidates → reporting 94 to prevent import (no deletions performed).")
    info("Summary: 0 removed (blocked during Test). Mode: TEST")
    sys.exit(POSTPROCESS_ERROR)

# ---------- Act ----------
removed_files = 0
removed_dirs = 0
removed_mb_total = 0.0

QUAR_DIR = DEST_DIR / "_samples_quarantine"

def _safe_move(src: Path):
    dst = QUAR_DIR / src.resolve().relative_to(DEST_DIR)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))

# Directories
if REMOVE_DIRS:
    for d in dir_candidates:
        rel = d.resolve().relative_to(DEST_DIR)
        if TEST_MODE:
            info(f"[TEST] Would remove directory: {rel}")
        else:
            if QUARANTINE_MODE:
                # Move contents into quarantine, then remove empty dirs
                moved_any = False
                for p in d.rglob("*"):
                    if p.is_file():
                        try:
                            _safe_move(p)
                            moved_any = True
                        except Exception as ex:
                            errors += 1
                            error(f"Quarantine move failed {p}: {ex}")
                # attempt to remove the now-empty tree
                try:
                    for sub in sorted(d.rglob("*"), reverse=True):
                        if sub.is_dir():
                            try:
                                sub.rmdir()
                            except:
                                pass
                    d.rmdir()
                except:
                    pass
                if moved_any:
                    removed_dirs += 1
                    info(f"[QUARANTINE] Directory contents moved: {rel}")
            else:
                try:
                    shutil.rmtree(d)
                    removed_dirs += 1
                    info(f"Removed directory: {rel}")
                except Exception as ex:
                    errors += 1
                    error(f"Failed to remove directory: {rel} - {ex}")
else:
    debug("Configured to keep directories (NZBPO_REMOVEDIRECTORIES=No)")

# Files
if REMOVE_FILES:
    for f_tuple in file_candidates:
        f, mb, *_ = f_tuple
        rel = f.resolve().relative_to(DEST_DIR)
        if TEST_MODE:
            info(f"[TEST] Would remove file: {rel} ({mb:.1f} MB)")
        else:
            if QUARANTINE_MODE:
                try:
                    QUAR_DIR.mkdir(parents=True, exist_ok=True)
                    _safe_move(f)
                    removed_files += 1
                    removed_mb_total += mb
                    info(f"[QUARANTINE] {rel} ({mb:.1f} MB)")
                except Exception as ex:
                    errors += 1
                    error(f"Quarantine move failed: {rel} - {ex}")
            else:
                try:
                    f.unlink()
                    removed_files += 1
                    removed_mb_total += mb
                    info(f"Removed file: {rel} ({mb:.1f} MB)")
                except Exception as ex:
                    errors += 1
                    error(f"Failed to remove file: {rel} - {ex}")
else:
    debug("Configured to keep files (NZBPO_REMOVEFILES=No)")

mode = "TEST" if TEST_MODE else ("LIVE+QUARANTINE" if QUARANTINE_MODE else "LIVE")
info(
    f"Summary: removed {removed_files} files / {removed_dirs} dirs "
    f"({removed_mb_total:.1f} MB). Mode: {mode}. "
    f"FilesChecked={files_considered} DirsChecked={dirs_considered} "
    f"Candidates={len(file_candidates)+len(dir_candidates)} "
    f"Rel%={'disabled' if EFF_RELATIVE_PERCENT < 0 else EFF_RELATIVE_PERCENT} "
    f"VideoMB>={VIDEO_MIN_MB}"
)

if errors > 0:
    sys.exit(POSTPROCESS_ERROR)

if removed_files == 0 and removed_dirs == 0 and len(file_candidates) == 0 and len(dir_candidates) == 0:
    sys.exit(POSTPROCESS_NONE)

# Optional quarantine purge after action
if QUARANTINE_MODE and QUARANTINE_MAX_AGE_DAYS > 0 and QUAR_DIR.exists():
    cutoff = time.time() - (QUARANTINE_MAX_AGE_DAYS * 86400)
    try:
        for p in QUAR_DIR.rglob("*"):
            try:
                if p.is_file() and p.stat().st_mtime < cutoff:
                    p.unlink()
            except Exception as ex:
                error(f"Quarantine purge failed at {p}: {ex}")
    except Exception:
        pass

sys.exit(POSTPROCESS_SUCCESS)