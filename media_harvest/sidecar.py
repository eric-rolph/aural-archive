"""
Aural Archive — JSON Sidecar Generator
=========================================
Generates companion .info.json metadata files alongside every
downloaded media file. Makes media searchable in tools like
Plex/Kodi and preserves provenance even when files are moved.

Inspired by MediaHelper's metadata sidecar pattern.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from . import __version__


def generate_sidecar(
    media_path: Path,
    info: dict,
    ytdlp_info_path: Path | None = None,
) -> Path:
    """
    Generate a .info.json sidecar file alongside *media_path*.

    Args:
        media_path: Path to the downloaded media file.
        info: Dict of harvest-level metadata (source_url, title, extractor, etc.)
        ytdlp_info_path: Optional path to a yt-dlp-generated .info.json to merge.

    Returns:
        Path to the written sidecar file.
    """
    sidecar_path = media_path.with_suffix(".info.json")

    # Start with yt-dlp metadata if available
    upstream = {}
    if ytdlp_info_path and ytdlp_info_path.exists():
        try:
            with open(ytdlp_info_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            # Extract the fields we care about from yt-dlp's verbose output
            upstream = {
                "title": raw.get("title") or "",
                "channel": raw.get("channel") or raw.get("uploader") or "",
                "description": raw.get("description") or "",
                "tags": raw.get("tags") or [],
                "upload_date": raw.get("upload_date") or "",
                "duration_seconds": raw.get("duration") or 0,
                "thumbnail": raw.get("thumbnail") or "",
                "view_count": raw.get("view_count"),
                "like_count": raw.get("like_count"),
                "categories": raw.get("categories") or [],
                "webpage_url": raw.get("webpage_url") or "",
            }
            # Clean up None values
            upstream = {k: v for k, v in upstream.items() if v is not None}

            # Remove the raw yt-dlp .info.json (we've merged what we need)
            try:
                ytdlp_info_path.unlink()
            except OSError:
                pass
        except (json.JSONDecodeError, OSError):
            pass

    # Build the merged sidecar
    sidecar = {
        "source_url": info.get("source_url") or upstream.get("webpage_url") or "",
        "title": info.get("title") or upstream.get("title") or media_path.stem,
        "channel": upstream.get("channel") or "",
        "description": upstream.get("description") or "",
        "tags": upstream.get("tags") or [],
        "upload_date": upstream.get("upload_date") or "",
        "duration_seconds": upstream.get("duration_seconds") or 0,
        "thumbnail": upstream.get("thumbnail") or "",
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "extractor": info.get("extractor") or "unknown",
        "format": info.get("format") or media_path.suffix.lstrip("."),
        "sample_rate": info.get("sample_rate"),
        "bit_depth": info.get("bit_depth"),
        "harvest_version": __version__,
    }

    # Add optional upstream stats
    if upstream.get("view_count"):
        sidecar["view_count"] = upstream["view_count"]
    if upstream.get("like_count"):
        sidecar["like_count"] = upstream["like_count"]
    if upstream.get("categories"):
        sidecar["categories"] = upstream["categories"]

    # Remove internal keys
    sidecar.pop("_ytdlp_info_file", None)

    # Clean None values
    sidecar = {k: v for k, v in sidecar.items() if v is not None}

    with open(sidecar_path, "w", encoding="utf-8") as f:
        json.dump(sidecar, f, indent=2, ensure_ascii=False)

    print(f"  📋  Sidecar: {sidecar_path.name}")
    return sidecar_path
