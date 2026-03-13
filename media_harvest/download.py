"""
Aural Archive — Acquisition Module
==================================
Acquires audio from digital repositories or local sources and converts
to production-ready WAV files. Supports archival search, batch, and direct
URL modes.

Delegates actual acquisition to the pluggable extractor system and
tracks job state via the SQLite journal for crash recovery.
"""

import json
import subprocess
import sys
from pathlib import Path

from . import config
from .extractors import get_extractor
from .headers import get_random_headers
from .state import StateManager
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
# Archival search via yt-dlp
# ─────────────────────────────────────────────────────────────────────────────

def yt_search(query: str, max_results: int = 5, max_duration: int = 600) -> list:
    """Search digital repositories via yt-dlp and return a list of result dicts."""
    yt_dlp = config.get_yt_dlp()
    headers = get_random_headers()

    cmd = [
        yt_dlp,
        f"ytsearch{max_results}:{query}",
        "--dump-json",
        "--flat-playlist",
        "--no-download",
        "--user-agent", headers["User-Agent"],
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
# Download via extractor system
# ─────────────────────────────────────────────────────────────────────────────

def download_and_convert(
    url: str,
    output_dir: Path,
    sample_rate: int = 44100,
    bit_depth: int = 16,
    title_hint: str = "",
    output_format: str = "wav",
) -> dict | None:
    """
    Acquire audio from *url* via the best-matching extractor.
    Returns a manifest entry dict on success, or None on failure.
    """
    extractor = get_extractor(url)
    print(f"  🔌  Using extractor: {extractor.name}")
    return extractor.download(
        url=url,
        output_dir=output_dir,
        sample_rate=sample_rate,
        bit_depth=bit_depth,
        output_format=output_format,
        title_hint=title_hint,
    )


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

        print(f"\n  Found {len(unique)} unique recordings. Enter numbers to acquire (comma-separated),")
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

        with StateManager(project) as state:
            for r in to_download:
                # Register in state journal
                state.add_job(r["url"], category=cat_id, title=r["title"])

                if state.is_completed(r["url"]):
                    print(f"  ⏭  Already completed: {r['title']}")
                    continue

                state.start_job(r["url"], extractor=get_extractor(r["url"]).name)
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
                    state.complete_job(r["url"], result_file=entry.get("file", ""))
                else:
                    state.fail_job(r["url"], error="Download or conversion failed")


def mode_batch(project: str, presets: dict, category: str | None,
               max_results: int, max_duration: int, sample_rate: int,
               bit_depth: int, dry_run: bool, retry_failed: bool = False):
    """Batch mode: auto-acquire top N results for each search term."""
    cats = [category] if category else get_category_ids(presets)
    manifest = load_manifest(project)

    with StateManager(project) as state:
        # Crash recovery: reset any stuck in_progress jobs
        state.reset_in_progress()

        # Retry failed jobs if requested
        if retry_failed:
            failed = state.get_failed()
            if failed:
                print(f"\n  🔄  Retrying {len(failed)} previously failed jobs...")
                state.reset_failed()

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
                    url = r["url"]

                    # Register in state journal
                    state.add_job(url, category=cat_id, title=r["title"])

                    # Skip if already completed
                    if state.is_completed(url):
                        print(f"  ⏭  Already completed: {r['title']}")
                        continue

                    # Also check manifest for backward compat
                    if any(m.get("source_url") == url for m in manifest):
                        print(f"  ⏭  Already in manifest: {r['title']}")
                        state.complete_job(url, result_file="manifest-legacy")
                        continue

                    extractor = get_extractor(url)
                    state.start_job(url, extractor=extractor.name)

                    entry = download_and_convert(
                        url, out_dir,
                        sample_rate=sample_rate,
                        bit_depth=bit_depth,
                        title_hint=r["title"],
                    )
                    if entry:
                        entry["category"] = cat_id
                        manifest.append(entry)
                        save_manifest(project, manifest)
                        state.complete_job(url, result_file=entry.get("file", ""))
                    else:
                        state.fail_job(url, error="Download or conversion failed")

        # Print journal summary
        counts = state.get_counts()
        print(f"\n  📊  Journal: {counts.get('completed', 0)} completed, "
              f"{counts.get('failed', 0)} failed, "
              f"{counts.get('pending', 0)} pending")

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

    with StateManager(project) as state:
        state.add_job(url, category=category)

        if state.is_completed(url):
            print(f"  ⏭  Already completed: {url}")
            return

        extractor = get_extractor(url)
        state.start_job(url, extractor=extractor.name)

        entry = download_and_convert(
            url, out_dir,
            sample_rate=sample_rate,
            bit_depth=bit_depth,
        )
        if entry:
            entry["category"] = category
            manifest.append(entry)
            save_manifest(project, manifest)
            state.complete_job(url, result_file=entry.get("file", ""))
            print(f"\n  ✓  Saved and logged.")
        else:
            state.fail_job(url, error="Acquisition or conversion failed")
            print(f"\n  ✗  Acquisition failed. Run with --retry-failed to retry later.")
