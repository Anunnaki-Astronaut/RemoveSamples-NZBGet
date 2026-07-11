# AGENTS.md — RemoveSamples-NZBGet

Briefing for coding agents and new maintainers working on this repo. Keep changes safe, small, and well tested.

## 1) What this project does
RemoveSamples-NZBGet is a Post-Processing extension for NZBGet v23+. It finds and removes “sample” clips and junk assets from completed downloads using name patterns and size thresholds. It only performs destructive actions when the overall download status indicates success.

Goals:
- Idempotent and predictable runs
- Contract correctness
- Clear, minimal logs with a one-line summary
- Cross-platform behavior on Windows and Linux

Execution order: after ExtendedUnpacker, before Clean and before media managers scan the payload.

## 2) Contract snapshot

Exit codes:
- `POSTPROCESS_SUCCESS = 93`
- `POSTPROCESS_ERROR   = 94`
- `POSTPROCESS_NONE    = 95`

Env vars read at runtime:

**Required**
- `NZBPP_DIRECTORY`
- `NZBPP_STATUS` with fallback `NZBPP_TOTALSTATUS`

**Optional**
- `NZBPP_NZBNAME`
- `NZBPP_CATEGORY`

Required options provided as env vars:
- `NZBPO_REMOVEDIRECTORIES`
- `NZBPO_REMOVEFILES`
- `NZBPO_DEBUG`
- `NZBPO_VIDEOSIZETHRESHOLDMB`
- `NZBPO_VIDEOEXTS`
- `NZBPO_AUDIOSIZETHRESHOLDMB`
- `NZBPO_AUDIOEXTS`

Optional toggles (read only if present, some land in v1.1.0):
- `NZBPO_TESTMODE`
- `NZBPO_BLOCKIMPORTDURINGTEST`
- `NZBPO_RELATIVEPERCENT`
- `NZBPO_PROTECTEDPATHS`
- `NZBPO_DENYPATTERNS`
- `NZBPO_IMAGESAMPLES`
- `NZBPO_JUNKEXTRAS`
- `NZBPO_CATEGORYTHRESHOLDS`
- `NZBPO_QUARANTINEMODE`
- `NZBPO_QUARANTINEMAXAGEDAYS`

If you need a new `NZBPO_*` key, open an issue first.

## 3) Detection model
- Name patterns: case-insensitive matches for words like `sample`, common dot variants, and typical scene junk. Never hard-code titles. Prefer pattern lists that are user configurable.
- Size thresholds: treat very small video or audio as samples. Defaults come from the options above. Relative-percent can be used when enabled.
- Category overrides: when enabled, thresholds may vary by `NZBPP_CATEGORY`.

## 4) Safety rules
- If `NZBPP_STATUS` or `NZBPP_TOTALSTATUS` is not success, exit 95 without changing files.
- **Perform deletions or moves only when `NZBPO_REMOVEFILES=yes` or `NZBPO_REMOVEDIRECTORIES=yes`. When `NZBPO_TESTMODE=yes`, never modify files (simulate only).**
- Never traverse above `NZBPP_DIRECTORY`. Reject symlinks.
- Respect `PROTECTEDPATHS` and deny lists. When quarantine is enabled, move to `_samples_quarantine` and optionally purge by age.
- Keep the Windows UTF-8 console safeguard near the top of `main.py` so debug logs do not throw `UnicodeEncodeError`.
- Never traverse above `NZBPP_DIRECTORY`. Reject symlinks and Windows junctions.

## 5) Logs
- `[INFO]` actions, `[ERROR]` failures, `[DEBUG]` only when `NZBPO_DEBUG` is true.
- Always print one final summary line, for example:
  `Summary: removed 2 files, 1 dir; quarantined 0; errors 0; exit=93`
- Return the correct exit code.

## 6) Local test recipes

Linux or macOS (bash):
```bash
export NZBPP_DIRECTORY="/abs/path/to/testdir"
export NZBPP_STATUS=SUCCESS
export NZBPO_REMOVEDIRECTORIES=yes
export NZBPO_REMOVEFILES=yes
export NZBPO_DEBUG=no
export NZBPO_VIDEOSIZETHRESHOLDMB=150
export NZBPO_VIDEOEXTS=".mkv,.mp4,.avi,.mov,.ts,.m4v"
export NZBPO_AUDIOSIZETHRESHOLDMB=2
export NZBPO_AUDIOEXTS=".mp3,.flac,.m4a,.ogg,.wav"
export NZBPO_TESTMODE=yes
# Optional toggles:
# export NZBPO_BLOCKIMPORTDURINGTEST=yes
# export NZBPO_QUARANTINEMODE=yes
# export NZBPO_QUARANTINEMAXAGEDAYS=30

python3 main.py; echo "exit=$?"
```

Windows PowerShell:
```powershell
$env:NZBPP_DIRECTORY = "C:\Path\To\testdir"
$env:NZBPP_STATUS = "SUCCESS"
$env:NZBPO_REMOVEDIRECTORIES = "yes"
$env:NZBPO_REMOVEFILES = "yes"
$env:NZBPO_DEBUG = "no"
$env:NZBPO_VIDEOSIZETHRESHOLDMB = "150"
$env:NZBPO_VIDEOEXTS = ".mkv,.mp4,.avi,.mov,.ts,.m4v"
$env:NZBPO_AUDIOSIZETHRESHOLDMB = "2"
$env:NZBPO_AUDIOEXTS = ".mp3,.flac,.m4a,.ogg,.wav"
$env:NZBPO_TESTMODE = "yes"
# Optional toggles (uncomment as needed)
# $env:NZBPO_BLOCKIMPORTDURINGTEST = "yes"
# $env:NZBPO_QUARANTINEMODE = "yes"
# $env:NZBPO_QUARANTINEMAXAGEDAYS = "30"

python .\main.py; echo "exit=$LASTEXITCODE"
```

Test corpus guidelines:
- Include nested `sample` folders, tiny audio, a few image assets, long and Unicode paths. Verify summary text and exit code.

## 7) Coding guidelines
- Keep env parsing helpers tight and explicit. Do not assume casing or presence.
- Avoid OS-specific path assumptions. Use `pathlib` where possible.
- Do not hard-code user policy. Use options and flags.

## 8) Versioning and PR checklist
- Increment version when behavior changes and update the changelog.
- PR title in imperative mood and scoped, for example: `fix: honor ProtectedPaths under dry run`.
- Include what you tested, on which OS, and the observed exit code.
- Acceptance criteria:
  - Contract header values unchanged
  - Required env keys and option names intact
  - One summary line in logs
  - Windows UTF-8 safeguard present
  - Local smoke test completed

## 9) Common tasks
- Adjust thresholds: change option defaults and descriptions, not the detection core.
- Add deny pattern: extend `NZBPO_DENYPATTERNS` list, not hard-coded checks.
- Protect a file or dir: add to `NZBPO_PROTECTEDPATHS`.
- Enable quarantine: set `QuarantineMode=Yes`, optionally `QuarantineMaxAgeDays>0`.

## 10) Ownership
If uncertain, run a one-minute local simulation and include 2–3 bullets of findings in the PR.

Maintainer: Anunnaki-Astronaut

URL: https://github.com/Anunnaki-Astronaut/RemoveSamples-NZBGet

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
