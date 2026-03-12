"""
Shared utilities for Media Harvest.
"""

import re


def sanitize_filename(name: str, max_length: int = 120) -> str:
    """Remove characters that are problematic in filenames."""
    keepchars = (" ", ".", "_", "-")
    cleaned = "".join(c if c.isalnum() or c in keepchars else "_" for c in name).strip()
    return cleaned[:max_length]


def format_duration(seconds: float) -> str:
    """Format seconds as M:SS or H:MM:SS."""
    if seconds <= 0:
        return "??:??"
    total = int(seconds)
    if total >= 3600:
        h, remainder = divmod(total, 3600)
        m, s = divmod(remainder, 60)
        return f"{h}:{m:02d}:{s:02d}"
    m, s = divmod(total, 60)
    return f"{m}:{s:02d}"


def get_video_id(url: str) -> str | None:
    """Extract video ID from common YouTube URL formats."""
    if "youtu.be" in url:
        return url.split("/")[-1].split("?")[0]
    if "youtube.com" in url:
        if "v=" in url:
            return url.split("v=")[1].split("&")[0]
    return None
