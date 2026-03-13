"""
Configuration management for Aural Archive.

Handles auto-detection of ffmpeg/ffprobe/yt-dlp, .env loading,
and project directory structure.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the repo root (two levels up from this file)
REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

# ─────────────────────────────────────────────────────────────────────────────
# Tool paths — auto-detected, overridable via .env
# ─────────────────────────────────────────────────────────────────────────────

_FFMPEG_PATH = None
_FFPROBE_PATH = None
_YT_DLP_PATH = None


def _find_executable(name: str, env_var: str, known_paths: list[str] | None = None) -> str:
    """Find an executable by checking (in order): env var, PATH, known locations."""
    # 1. Check environment variable
    env_val = os.environ.get(env_var)
    if env_val and Path(env_val).exists():
        return env_val

    # 2. Check system PATH
    found = shutil.which(name)
    if found:
        return found

    # 3. Check known Windows locations
    if known_paths:
        for p in known_paths:
            expanded = os.path.expandvars(p)
            if Path(expanded).exists():
                return expanded

    # 4. Broad search under AppData (Windows-specific, for pip --user installs)
    if name == "yt-dlp" or name == "yt-dlp.exe":
        appdata = Path.home() / "AppData"
        if appdata.exists():
            for p in appdata.rglob(f"{name}.exe"):
                return str(p)

    return ""


def get_ffmpeg() -> str:
    """Return path to ffmpeg executable."""
    global _FFMPEG_PATH
    if _FFMPEG_PATH:
        return _FFMPEG_PATH
    _FFMPEG_PATH = _find_executable("ffmpeg", "FFMPEG_PATH", [
        r"C:\Users\ericr\ffmpeg-full-temp\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
    ])
    if not _FFMPEG_PATH:
        print("ERROR: ffmpeg not found. Install it or set FFMPEG_PATH in .env")
        sys.exit(1)
    return _FFMPEG_PATH


def get_ffprobe() -> str:
    """Return path to ffprobe executable."""
    global _FFPROBE_PATH
    if _FFPROBE_PATH:
        return _FFPROBE_PATH
    _FFPROBE_PATH = _find_executable("ffprobe", "FFPROBE_PATH", [
        r"C:\Users\ericr\ffmpeg-full-temp\ffmpeg-8.0.1-full_build\bin\ffprobe.exe",
        r"C:\ffmpeg\bin\ffprobe.exe",
    ])
    if not _FFPROBE_PATH:
        print("ERROR: ffprobe not found. Install ffmpeg or set FFPROBE_PATH in .env")
        sys.exit(1)
    return _FFPROBE_PATH


def get_yt_dlp() -> str:
    """Return path to yt-dlp executable."""
    global _YT_DLP_PATH
    if _YT_DLP_PATH:
        return _YT_DLP_PATH
    _YT_DLP_PATH = _find_executable("yt-dlp", "YT_DLP_PATH")
    if not _YT_DLP_PATH:
        print("ERROR: yt-dlp not found. Install with: pip install yt-dlp")
        sys.exit(1)
    return _YT_DLP_PATH


# ─────────────────────────────────────────────────────────────────────────────
# Project structure
# ─────────────────────────────────────────────────────────────────────────────

PROJECTS_DIR = REPO_ROOT / "projects"


def get_project_dir(project_name: str) -> Path:
    """Return the root directory for a named project."""
    return PROJECTS_DIR / project_name


def get_project_output_dir(project_name: str) -> Path:
    """Return the output/ directory for downloaded files."""
    return get_project_dir(project_name) / "output"


def get_project_samples_dir(project_name: str) -> Path:
    """Return the samples/ directory for extracted clips."""
    return get_project_dir(project_name) / "samples"


def get_project_presets_file(project_name: str) -> Path:
    """Return path to the project's search presets JSON."""
    return get_project_dir(project_name) / "presets.json"


def get_project_extractions_file(project_name: str) -> Path:
    """Return path to the project's extraction map JSON."""
    return get_project_dir(project_name) / "extractions.json"


def get_project_manifest_file(project_name: str) -> Path:
    """Return path to the project's download manifest."""
    return get_project_output_dir(project_name) / "manifest.json"


def get_project_transcripts_file(project_name: str) -> Path:
    """Return path to the project's transcript manifest."""
    return get_project_output_dir(project_name) / "transcripts.json"
