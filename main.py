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
from pathlib import Path

# Force UTF-8 console on Windows to avoid UnicodeEncodeError in debug logs
if os.name == "nt":
    try:
        # Python 3.7+
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        # Fallback for older Pythons / odd consoles
        try:
            import codecs
            sys.stdout = codecs.getwriter("utf-8")(getattr(sys.stdout, "buffer", sys.stdout), "replace")
            sys.stderr = codecs.getwriter("utf-8")(getattr(sys.stderr, "buffer", sys.stderr), "replace")
        except Exception:
            pass  # Continue without changes if everything fails

# --- NZBGet exit codes -----------------------------------------------------
POSTPROCESS_SUCCESS = 93
POSTPROCESS_ERROR = 94
POSTPROCESS_NONE = 95

print("[DETAIL] RemoveSamples extension started")
sys.stdout.flush()

# Check required options
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
            f"[ERROR] Option {optname[6:]} is missing in configuration "
            f"file. Please check script settings"
        )
        print(error_msg)
        sys.exit(POSTPROCESS_ERROR)

# ── Read NZBGet variables & user options ───────────────────────────────────
DEBUG = os.environ.get('NZBPO_DEBUG', 'No').lower() in (
    'yes', 'y', 'true', '1'
)
REM_DIRS = os.environ.get('NZBPO_REMOVEDIRECTORIES', 'Yes').lower() in (
    'yes', 'y', 'true', '1'
)
REM_FILES = os.environ.get('NZBPO_REMOVEFILES', 'Yes').lower() in (
    'yes', 'y', 'true', '1'
)
VID_LIMIT = int(os.environ.get('NZBPO_VIDEOSIZETHRESHOLDMB', '150') or '0')
AUD_LIMIT = int(os.environ.get('NZBPO_AUDIOSIZETHRESHOLDMB', '2') or '0')

VIDEO_EXTS = {
    e if e.startswith('.') else f'.{e}'
    for e in os.environ.get(
        'NZBPO_VIDEOEXTS',
        '.mkv,.mp4,.avi,.mov,.wmv,.flv,.webm,.ts,.m4v,.vob'
    ).split(',') if e.strip()
}

AUDIO_EXTS = {
    e if e.startswith('.') else f'.{e}'
    for e in os.environ.get(
        'NZBPO_AUDIOEXTS',
        '.wav,.aiff,.mp3,.flac,.m4a,.ogg,.aac,.alac,.ape,.opus,.wma'
    ).split(',') if e.strip()
}

DL_DIR = os.environ.get('NZBPP_DIRECTORY')
DL_STATUS = os.environ.get('NZBPP_STATUS', '') or os.environ.get('NZBPP_TOTALSTATUS', '')
DL_NAME = os.environ.get('NZBPP_NZBNAME', '')


def log(level, message):
    """Log a message with the specified level."""
    print(f"[{level}] {message}")


def debug_log(message):
    """Log a debug message if debug mode is enabled."""
    if DEBUG:
        log("DEBUG", message)


# ── Regex patterns ─────────────────────────────────────────────────────────
FILE_PATTERNS = [
    r'\bsample\b', r'\.sample\.', r'^sample\.', r'_sample\.', r'-sample\.',
    r'sample[_-]'
]
DIR_PATTERNS = [r'\bsamples?\b', r'^samples?$']

FILE_RE = [re.compile(pattern, re.I) for pattern in FILE_PATTERNS]
DIR_RE = [re.compile(pattern, re.I) for pattern in DIR_PATTERNS]


def is_sample_file(path):
    """Check if a file is considered a sample based on name and size."""
    name = path.name
    if any(regex.search(name) for regex in FILE_RE):
        return True
    
    ext = path.suffix.lower()
    try:
        size_mb = path.stat().st_size / (1 << 20)
    except OSError:
        return False

    if ext in VIDEO_EXTS and VID_LIMIT and size_mb <= VID_LIMIT:
        return True
    if ext in AUDIO_EXTS and AUD_LIMIT and size_mb <= AUD_LIMIT:
        return True
    return False


def is_sample_dir(dir_name):
    """Check if a directory name matches sample patterns."""
    return any(regex.search(dir_name) for regex in DIR_RE)


def remove_samples(root):
    """Remove sample files and directories from the specified root path."""
    removed = []
    for path in sorted(root.rglob('*'), reverse=True):
        if path.is_file() and REM_FILES and is_sample_file(path):
            path.unlink(missing_ok=True)
            removed.append(str(path))
            log("INFO", f"Removed file {path.relative_to(root)}")
        elif path.is_dir() and REM_DIRS and is_sample_dir(path.name):
            shutil.rmtree(path, ignore_errors=True)
            removed.append(str(path))
            log("INFO", f"Removed dir  {path.relative_to(root)}")
    return removed


def main():
    """Main entry point for the RemoveSamples extension."""
    # Check if running in post-processing mode
    if not DL_DIR:
        error_msg = (
            "NZBPP_DIRECTORY missing - script must run in "
            "post-processing mode"
        )
        log("ERROR", error_msg)
        sys.exit(POSTPROCESS_ERROR)

    if not DL_STATUS.upper().startswith('SUCCESS'):
        log("INFO", f"Status {DL_STATUS}; skipping.")
        sys.exit(POSTPROCESS_NONE)

    if not os.path.exists(DL_DIR):
        log("ERROR", f"Destination directory doesn't exist: {DL_DIR}")
        sys.exit(POSTPROCESS_NONE)

    log("INFO", f'Processing "{DL_NAME}" in {DL_DIR}')
    
    debug_info = (
        f"dirs={REM_DIRS}, files={REM_FILES}, "
        f"vid≤{VID_LIMIT} MB, aud≤{AUD_LIMIT} MB, "
        f"vExt={sorted(VIDEO_EXTS)}, aExt={sorted(AUDIO_EXTS)}"
    )
    debug_log(debug_info)

    removed_count = len(remove_samples(Path(DL_DIR)))
    log("INFO", f"Removed {removed_count} sample item(s)")

    print("[DETAIL] RemoveSamples extension completed successfully")
    sys.exit(POSTPROCESS_SUCCESS)


if __name__ == '__main__':
    main()
