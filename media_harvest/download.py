"""
Media Harvest — Download Module
================================
Downloads audio from YouTube (or any yt-dlp-supported site) and converts
to production-ready WAV files. Supports search, batch, and direct URL modes.

Generalized from the auction-audio-pipeline project.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .utils import sanitize_filename, format_duration


# ─────────────────────────────────────────────────────────────────────────────
# Manifest I/O
# ─────────────────────────────────────────────────────────────────────────────

def load_manifest(project: str) -> list:
    manifest_file = config.get_project_manifest_file(project)
    if manifest_file.exists():
        with open(manifest_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_manifest(project: str, entries: list):
    manifest_file = config.get_project_manifest_file(project)
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


# ─────────────────────────────────────────────────────────────────────────────
# Presets
# ─────────────────────────────────────────────────────────────────────────────

def load_presets(project: str) -> dict:
    presets_file = config.get_project_presets_file(project)
    if not presets_file.exists():
        print(f"ERROR: No presets.json found at {presets_file}")
        print(f"Create one or use 'media_harvest init {project}' to generate a template.")
        sys.exit(1)
    with open(presets_file, "r", encoding="utf-8") as f:
        return json.load(f)


def get_category_ids(presets: dict) -> list[str]:
    """Return sorted list of category IDs from presets."""
    return sorted(presets.get("categories", {}).keys())


def ensure_output_dirs(project: str, presets: dict):
    """Create output subdirectories for each category."""
    output_dir = config.get_project_output_dir(project)
    for cat_id in get_category_ids(presets):
        (output_dir / cat_id).mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# YouTube search via yt-dlp
# ─────────────────────────────────────────────────────────────────────────────

def yt_search(query: str, max_results: int = 5, max_duration: int = 600) -> list:
    """Search YouTube via yt-dlp and return a list of result dicts."""
    yt_dlp = config.get_yt_dlp()
    cmd = [
        yt_dlp,
        f"ytsearch{max_results}:{query}",
        "--dump-json",
        "--flat-playlist",
        "--no-download",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    entries = []
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        duration = entry.get("duration") or 0
        if max_duration and duration > max_duration:
            continue
        entries.append({
            "id": entry.get("id", ""),
            "title": entry.get("title", "Unknown"),
            "url": entry.get("url") or entry.get("webpage_url") or f"https://www.youtube.com/watch?v={entry.get('id', '')}",
            "duration": duration,
            "channel": entry.get("channel") or entry.get("uploader") or "Unknown",
        })
    return entries


def display_results(results: list, query: str):
    """Pretty-print search results."""
    print(f"\n{'─' * 70}")
    print(f'  Search: "{query}"  ({len(results)} results)')
    print(f"{'─' * 70}")
    for i, r in enumerate(results, 1):
        dur = format_duration(r["duration"]) if r["duration"] else "??:??"
        print(f"  [{i}]  {r['title']}")
        print(f"       Channel: {r['channel']}  |  Duration: {dur}")
        print(f"       URL: {r['url']}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Download & Convert
# ─────────────────────────────────────────────────────────────────────────────

def _find_latest_file(directory: Path) -> Path | None:
    """Find the most recently modified file in directory (non-recursive)."""
    files = [f for f in directory.iterdir() if f.is_file() and f.suffix.lower() != ".json"]
    if not files:
        return None
    return max(files, key=lambda f: f.stat().st_mtime)


def _get_duration(path: Path) -> float:
    """Use ffprobe to get duration in seconds."""
    ffprobe = config.get_ffprobe()
    cmd = [
        ffprobe,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def download_and_convert(
    url: str,
    output_dir: Path,
    sample_rate: int = 44100,
    bit_depth: int = 16,
    title_hint: str = "",
    output_format: str = "wav",
) -> dict | None:
    """
    Download audio from *url* via yt-dlp, convert to the target format via ffmpeg.
    Returns a manifest entry dict on success, or None on failure.
    """
    yt_dlp = config.get_yt_dlp()
    ffmpeg = config.get_ffmpeg()

    # Step 1: Download best audio with yt-dlp
    tmp_template = str(output_dir / "%(title)s.%(ext)s")
    cmd_dl = [
        yt_dlp,
        "--no-playlist",
        "-x",                          # extract audio
        "--audio-format", "wav",       # let yt-dlp try wav first
        "--ffmpeg-location", str(Path(ffmpeg).parent),
        "-o", tmp_template,
        "--no-overwrites",
        url,
    ]

    print(f"  ⬇  Downloading: {url}")
    dl_result = subprocess.run(cmd_dl, capture_output=True, text=True, encoding="utf-8")

    if dl_result.returncode != 0:
        # Fallback: download as best audio, then convert manually
        print("  ⚠  Direct WAV failed, trying fallback download...")
        cmd_dl_fb = [
            yt_dlp,
            "--no-playlist",
            "-x",
            "--audio-format", "best",
            "--ffmpeg-location", str(Path(ffmpeg).parent),
            "-o", tmp_template,
            "--no-overwrites",
            url,
        ]
        dl_result = subprocess.run(cmd_dl_fb, capture_output=True, text=True, encoding="utf-8")
        if dl_result.returncode != 0:
            print(f"  ✗  Download FAILED for: {url}")
            print(f"     stderr: {dl_result.stderr[:300]}")
            return None

    # Find the downloaded file (most recent in output_dir)
    downloaded_file = _find_latest_file(output_dir)
    if not downloaded_file:
        print(f"  ✗  Could not find downloaded file in {output_dir}")
        return None

    print(f"  ✓  Downloaded: {downloaded_file.name}")

    # Step 2: Convert to target format with precise specs via ffmpeg
    out_name = sanitize_filename(downloaded_file.stem) + f".{output_format}"
    out_path = output_dir / out_name

    # Determine codec string for bit depth
    codec_map = {16: "pcm_s16le", 24: "pcm_s24le", 32: "pcm_s32le"}
    codec = codec_map.get(bit_depth, "pcm_s16le")

    if downloaded_file == out_path:
        tmp_path = output_dir / (sanitize_filename(downloaded_file.stem) + "_tmp.wav")
        downloaded_file.rename(tmp_path)
        downloaded_file = tmp_path

    cmd_ff = [
        ffmpeg,
        "-y",
        "-i", str(downloaded_file),
        "-ar", str(sample_rate),
        "-ac", "2",                   # stereo
        "-acodec", codec,
        "-f", output_format,
        str(out_path),
    ]

    print(f"  ⚙  Converting to {output_format.upper()} ({sample_rate} Hz, {bit_depth}-bit)...")
    ff_result = subprocess.run(cmd_ff, capture_output=True, text=True, encoding="utf-8")

    if ff_result.returncode != 0:
        print(f"  ✗  FFmpeg conversion FAILED")
        print(f"     stderr: {ff_result.stderr[:300]}")
        return None

    # Clean up intermediate file
    if downloaded_file.exists() and downloaded_file != out_path:
        downloaded_file.unlink()

    # Get duration of output file
    duration = _get_duration(out_path)

    print(f"  ✓  Output: {out_path.name}  ({duration:.1f}s)")

    return {
        "file": str(out_path.name),
        "source_url": url,
        "title": title_hint or out_path.stem,
        "duration_seconds": round(duration, 2),
        "sample_rate": sample_rate,
        "bit_depth": bit_depth,
        "format": output_format,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Modes
# ─────────────────────────────────────────────────────────────────────────────

def mode_search(project: str, presets: dict, category: str | None,
                max_results: int, max_duration: int, sample_rate: int,
                bit_depth: int, dry_run: bool):
    """Interactive search mode: show results, let user pick."""
    cats = [category] if category else get_category_ids(presets)

    for cat_id in cats:
        cat = presets["categories"][cat_id]
        print(f"\n{'═' * 70}")
        print(f"  CATEGORY: {cat['label']}")
        print(f"  {cat.get('description', '')}")
        print(f"{'═' * 70}")

        all_results = []
        for term in cat["search_terms"]:
            results = yt_search(term, max_results=max_results, max_duration=max_duration)
            display_results(results, term)
            all_results.extend(results)

        if dry_run:
            print("  [DRY RUN] Skipping downloads.\n")
            continue

        if not all_results:
            print("  No results found.\n")
            continue

        # Deduplicate by video ID
        seen = set()
        unique = []
        for r in all_results:
            if r["id"] not in seen:
                seen.add(r["id"])
                unique.append(r)

        print(f"\n  Found {len(unique)} unique videos. Enter numbers to download (comma-separated),")
        print(f"  'a' for all, or 'n' to skip:")
        for i, r in enumerate(unique, 1):
            dur = format_duration(r["duration"]) if r["duration"] else "??:??"
            print(f"    [{i}] {r['title']} ({dur})")

        choice = input("\n  > ").strip().lower()
        if choice == "n" or choice == "":
            continue

        if choice == "a":
            to_download = unique
        else:
            indices = [int(x.strip()) - 1 for x in choice.split(",") if x.strip().isdigit()]
            to_download = [unique[i] for i in indices if 0 <= i < len(unique)]

        manifest = load_manifest(project)
        out_dir = config.get_project_output_dir(project) / cat_id
        for r in to_download:
            entry = download_and_convert(
                r["url"], out_dir,
                sample_rate=sample_rate,
                bit_depth=bit_depth,
                title_hint=r["title"],
            )
            if entry:
                entry["category"] = cat_id
                manifest.append(entry)
                save_manifest(project, manifest)


def mode_batch(project: str, presets: dict, category: str | None,
               max_results: int, max_duration: int, sample_rate: int,
               bit_depth: int, dry_run: bool):
    """Batch mode: auto-download top N results for each search term."""
    cats = [category] if category else get_category_ids(presets)
    manifest = load_manifest(project)

    for cat_id in cats:
        cat = presets["categories"][cat_id]
        out_dir = config.get_project_output_dir(project) / cat_id
        print(f"\n{'═' * 70}")
        print(f"  BATCH: {cat['label']}")
        print(f"{'═' * 70}")

        for term in cat["search_terms"]:
            results = yt_search(term, max_results=max_results, max_duration=max_duration)
            display_results(results, term)

            if dry_run:
                print("  [DRY RUN] Skipping downloads.\n")
                continue

            for r in results:
                # Skip if already in manifest
                if any(m.get("source_url") == r["url"] for m in manifest):
                    print(f"  ⏭  Already downloaded: {r['title']}")
                    continue

                entry = download_and_convert(
                    r["url"], out_dir,
                    sample_rate=sample_rate,
                    bit_depth=bit_depth,
                    title_hint=r["title"],
                )
                if entry:
                    entry["category"] = cat_id
                    manifest.append(entry)
                    save_manifest(project, manifest)

    print(f"\n  Done. {len(manifest)} total files in manifest.")


def mode_url(project: str, presets: dict, url: str, category: str,
             sample_rate: int, bit_depth: int, dry_run: bool):
    """Download a single URL to a specific category."""
    if not category:
        cat_ids = get_category_ids(presets)
        if cat_ids:
            category = cat_ids[0]
            print(f"  No category specified, using default: {category}")
        else:
            print("ERROR: No categories defined in presets. Specify --category.")
            sys.exit(1)

    out_dir = config.get_project_output_dir(project) / category
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(project)

    if dry_run:
        print(f"  [DRY RUN] Would download: {url} → {category}")
        return

    entry = download_and_convert(
        url, out_dir,
        sample_rate=sample_rate,
        bit_depth=bit_depth,
    )
    if entry:
        entry["category"] = category
        manifest.append(entry)
        save_manifest(project, manifest)
        print(f"\n  ✓  Saved and logged.")
