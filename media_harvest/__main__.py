"""
Media Harvest — Unified CLI
=============================
Entry point for all media-harvest operations.

Usage:
    python -m media_harvest init <project>
    python -m media_harvest download --project <name> [--search|--batch|--url <URL>]
    python -m media_harvest transcribe --project <name> [--model base]
    python -m media_harvest extract --project <name>
    python -m media_harvest status --project <name>
"""

import argparse
import json
import sys
from pathlib import Path

from . import __version__, config
from .download import (
    load_presets, get_category_ids, ensure_output_dirs,
    mode_search, mode_batch, mode_url, load_manifest,
)
from .transcribe import batch_transcribe, load_transcripts
from .extract import run_extraction


# ─────────────────────────────────────────────────────────────────────────────
# Init command
# ─────────────────────────────────────────────────────────────────────────────

EXAMPLE_PRESETS = {
    "categories": {
        "01_vocals": {
            "label": "Vocals & Speech",
            "description": "Spoken word, speeches, vocals for sampling.",
            "search_terms": [
                "famous speech audio",
                "spoken word poetry"
            ],
            "keywords": ["speech", "vocal", "spoken"]
        },
        "02_ambient": {
            "label": "Ambient & Atmosphere",
            "description": "Environmental sounds, textures, room tones.",
            "search_terms": [
                "field recording nature",
                "urban ambient sound"
            ],
            "keywords": ["ambient", "texture", "atmosphere"]
        },
        "03_instruments": {
            "label": "Instruments & Music",
            "description": "Musical performances, instrument recordings.",
            "search_terms": [
                "street musician performance",
                "live concert audio"
            ],
            "keywords": ["music", "instrument", "live"]
        }
    }
}

EXAMPLE_EXTRACTIONS = {
    "01_intro_samples": [
        {
            "source": "01_vocals/example_file.wav",
            "clips": [
                {
                    "start": 0.0,
                    "end": 10.0,
                    "name": "intro_vocal_hook",
                    "note": "Opening vocal line for song intro"
                },
                {
                    "start": 15.0,
                    "end": 22.0,
                    "name": "verse_vocal",
                    "note": "Key phrase for verse section"
                }
            ]
        }
    ],
    "02_texture_layers": [
        {
            "source": "02_ambient/example_ambient.wav",
            "clips": [
                {
                    "start": 0.0,
                    "end": 30.0,
                    "name": "ambient_bed",
                    "note": "30s ambient texture for background layer"
                }
            ]
        }
    ]
}


def cmd_init(args):
    """Initialize a new project with template files."""
    project = args.project_name
    project_dir = config.get_project_dir(project)

    if project_dir.exists():
        print(f"  ⚠  Project '{project}' already exists at {project_dir}")
        response = input("  Overwrite template files? (y/n): ").strip().lower()
        if response != "y":
            return

    project_dir.mkdir(parents=True, exist_ok=True)
    config.get_project_output_dir(project).mkdir(parents=True, exist_ok=True)
    config.get_project_samples_dir(project).mkdir(parents=True, exist_ok=True)

    # Write template presets
    presets_file = config.get_project_presets_file(project)
    with open(presets_file, "w", encoding="utf-8") as f:
        json.dump(EXAMPLE_PRESETS, f, indent=2, ensure_ascii=False)

    # Write template extractions
    extractions_file = config.get_project_extractions_file(project)
    with open(extractions_file, "w", encoding="utf-8") as f:
        json.dump(EXAMPLE_EXTRACTIONS, f, indent=2, ensure_ascii=False)

    print(f"\n  ✓  Project '{project}' initialized at:")
    print(f"     {project_dir}")
    print(f"\n  Project structure:")
    print(f"     {project}/")
    print(f"     ├── presets.json       ← Edit: define your search categories & terms")
    print(f"     ├── extractions.json   ← Edit: define which clips to cut (after downloading)")
    print(f"     ├── output/            ← Downloads land here")
    print(f"     └── samples/           ← Extracted clips land here")
    print(f"\n  Next steps:")
    print(f"     1. Edit presets.json with your YouTube search terms")
    print(f"     2. python -m media_harvest download --project {project} --search")
    print(f"     3. python -m media_harvest transcribe --project {project}")
    print(f"     4. Edit extractions.json with timestamps from transcripts")
    print(f"     5. python -m media_harvest extract --project {project}")


# ─────────────────────────────────────────────────────────────────────────────
# Download command
# ─────────────────────────────────────────────────────────────────────────────

def cmd_download(args):
    """Download audio from YouTube."""
    project = args.project
    presets = load_presets(project)
    ensure_output_dirs(project, presets)

    cat_ids = get_category_ids(presets)
    category = args.category if args.category else None

    # Validate category
    if category and category not in cat_ids:
        print(f"ERROR: Category '{category}' not found in presets.")
        print(f"Available categories: {', '.join(cat_ids)}")
        sys.exit(1)

    print("=" * 70)
    print(f"  MEDIA HARVEST — DOWNLOAD")
    print(f"  Project: {project}")
    print(f"  Output: {args.output_format.upper()} PCM {args.bit_depth}-bit, {args.sample_rate} Hz, Stereo")
    print("=" * 70)

    if args.search:
        mode_search(project, presets, category,
                    args.max_results, args.max_duration,
                    args.sample_rate, args.bit_depth, args.dry_run)
    elif args.batch:
        mode_batch(project, presets, category,
                   args.max_results, args.max_duration,
                   args.sample_rate, args.bit_depth, args.dry_run)
    elif args.url:
        mode_url(project, presets, args.url, category,
                 args.sample_rate, args.bit_depth, args.dry_run)
    else:
        print("ERROR: Specify --search, --batch, or --url <URL>")
        sys.exit(1)

    print("\n  Pipeline complete.")
    manifest = load_manifest(project)
    if manifest:
        print(f"  Total files in manifest: {len(manifest)}")


# ─────────────────────────────────────────────────────────────────────────────
# Transcribe command
# ─────────────────────────────────────────────────────────────────────────────

def cmd_transcribe(args):
    """Transcribe all downloaded audio in a project."""
    batch_transcribe(
        project=args.project,
        model_size=args.model,
        category=args.category,
        force=args.force,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Extract command
# ─────────────────────────────────────────────────────────────────────────────

def cmd_extract(args):
    """Extract samples based on extractions.json."""
    run_extraction(
        project=args.project,
        sample_rate=args.sample_rate,
        bit_depth=args.bit_depth,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Status command
# ─────────────────────────────────────────────────────────────────────────────

def cmd_status(args):
    """Show status of a project."""
    project = args.project
    project_dir = config.get_project_dir(project)

    if not project_dir.exists():
        print(f"  Project '{project}' not found.")
        print(f"  Available projects:")
        projects_dir = config.PROJECTS_DIR
        if projects_dir.exists():
            for p in sorted(projects_dir.iterdir()):
                if p.is_dir() and not p.name.startswith("."):
                    print(f"    • {p.name}")
        else:
            print("    (none)")
        return

    print(f"\n  {'═' * 60}")
    print(f"  PROJECT: {project}")
    print(f"  {'═' * 60}")

    # Presets
    presets_file = config.get_project_presets_file(project)
    if presets_file.exists():
        with open(presets_file, "r", encoding="utf-8") as f:
            presets = json.load(f)
        cats = presets.get("categories", {})
        print(f"\n  📋 Categories: {len(cats)}")
        for cat_id, cat in cats.items():
            terms = len(cat.get("search_terms", []))
            print(f"     • {cat_id}: {cat.get('label', '')} ({terms} search terms)")
    else:
        print(f"\n  ⚠  No presets.json found")

    # Downloads
    output_dir = config.get_project_output_dir(project)
    manifest = load_manifest(project)
    print(f"\n  ⬇  Downloads: {len(manifest)} files")
    if output_dir.exists():
        for cat_dir in sorted(output_dir.iterdir()):
            if cat_dir.is_dir():
                audio_files = [f for f in cat_dir.iterdir()
                              if f.is_file() and f.suffix.lower() in {".wav", ".mp3", ".flac"}]
                if audio_files:
                    total_mb = sum(f.stat().st_size for f in audio_files) / (1024 * 1024)
                    print(f"     • {cat_dir.name}: {len(audio_files)} files ({total_mb:.1f} MB)")

    # Transcripts
    transcripts = load_transcripts(project)
    print(f"\n  🎙  Transcripts: {len(transcripts)} files")

    # Extractions
    extractions_file = config.get_project_extractions_file(project)
    if extractions_file.exists():
        with open(extractions_file, "r", encoding="utf-8") as f:
            extractions = json.load(f)
        total_clips = sum(
            len(clip)
            for sources in extractions.values()
            for source in sources
            for clip in [source.get("clips", [])]
        )
        print(f"\n  ✂️  Extraction map: {len(extractions)} categories, {total_clips} clips defined")
    else:
        print(f"\n  ✂️  No extractions.json (create one after reviewing transcripts)")

    # Samples
    samples_dir = config.get_project_samples_dir(project)
    if samples_dir.exists():
        sample_wavs = list(samples_dir.rglob("*.wav"))
        if sample_wavs:
            total_mb = sum(f.stat().st_size for f in sample_wavs) / (1024 * 1024)
            print(f"\n  🎵  Samples: {len(sample_wavs)} clips ({total_mb:.1f} MB)")
        else:
            print(f"\n  🎵  Samples: none extracted yet")

    print()


# ─────────────────────────────────────────────────────────────────────────────
# List command
# ─────────────────────────────────────────────────────────────────────────────

def cmd_list(args):
    """List all projects."""
    projects_dir = config.PROJECTS_DIR
    print(f"\n  MEDIA HARVEST — Projects")
    print(f"  {'─' * 50}")

    if not projects_dir.exists():
        print("  No projects found. Create one with: python -m media_harvest init <name>")
        return

    found = False
    for p in sorted(projects_dir.iterdir()):
        if p.is_dir() and not p.name.startswith(".") and not p.name.startswith("_"):
            found = True
            manifest = []
            manifest_file = p / "output" / "manifest.json"
            if manifest_file.exists():
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            print(f"  • {p.name}  ({len(manifest)} downloads)")

    if not found:
        print("  No projects found. Create one with: python -m media_harvest init <name>")

    print()


# ─────────────────────────────────────────────────────────────────────────────
# Main parser
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="media_harvest",
        description="Media Harvest — Download, transcribe, and extract audio samples from YouTube",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python -m media_harvest init my-song
  python -m media_harvest download --project my-song --search
  python -m media_harvest download --project my-song --url "https://youtube.com/watch?v=..."
  python -m media_harvest transcribe --project my-song
  python -m media_harvest extract --project my-song
  python -m media_harvest status --project my-song
  python -m media_harvest list
        """,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── init ──
    p_init = subparsers.add_parser("init", help="Initialize a new project")
    p_init.add_argument("project_name", help="Name for the new project")
    p_init.set_defaults(func=cmd_init)

    # ── download ──
    p_dl = subparsers.add_parser("download", help="Download audio from YouTube")
    p_dl.add_argument("--project", "-p", required=True, help="Project name")
    mode_group = p_dl.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--search", action="store_true",
                            help="Interactive search: browse results & pick")
    mode_group.add_argument("--batch", action="store_true",
                            help="Auto-download top N results for every search preset")
    mode_group.add_argument("--url", type=str, metavar="URL",
                            help="Download a single URL")
    p_dl.add_argument("--category", "-c", type=str, default=None,
                      help="Target a specific category (use category ID from presets.json)")
    p_dl.add_argument("--max-results", type=int, default=5,
                      help="Max search results per query (default: 5)")
    p_dl.add_argument("--max-duration", type=int, default=600,
                      help="Skip videos longer than N seconds (default: 600)")
    p_dl.add_argument("--sample-rate", type=int, default=44100,
                      help="WAV sample rate in Hz (default: 44100)")
    p_dl.add_argument("--bit-depth", type=int, choices=[16, 24, 32], default=16,
                      help="WAV bit depth (default: 16)")
    p_dl.add_argument("--output-format", default="wav", choices=["wav", "mp3", "flac"],
                      help="Output audio format (default: wav)")
    p_dl.add_argument("--dry-run", action="store_true",
                      help="Preview search results without downloading")
    p_dl.set_defaults(func=cmd_download)

    # ── transcribe ──
    p_tx = subparsers.add_parser("transcribe", help="Transcribe downloaded audio with Whisper")
    p_tx.add_argument("--project", "-p", required=True, help="Project name")
    p_tx.add_argument("--model", default="base",
                      choices=["tiny", "base", "small", "medium", "large"],
                      help="Whisper model size (default: base)")
    p_tx.add_argument("--category", "-c", type=str, default=None,
                      help="Only transcribe a specific category")
    p_tx.add_argument("--force", action="store_true",
                      help="Re-transcribe files that already have transcripts")
    p_tx.set_defaults(func=cmd_transcribe)

    # ── extract ──
    p_ex = subparsers.add_parser("extract", help="Extract clips based on extractions.json")
    p_ex.add_argument("--project", "-p", required=True, help="Project name")
    p_ex.add_argument("--sample-rate", type=int, default=44100,
                      help="WAV sample rate (default: 44100)")
    p_ex.add_argument("--bit-depth", type=int, choices=[16, 24, 32], default=16,
                      help="WAV bit depth (default: 16)")
    p_ex.set_defaults(func=cmd_extract)

    # ── status ──
    p_st = subparsers.add_parser("status", help="Show project status")
    p_st.add_argument("--project", "-p", required=True, help="Project name")
    p_st.set_defaults(func=cmd_status)

    # ── list ──
    p_ls = subparsers.add_parser("list", help="List all projects")
    p_ls.set_defaults(func=cmd_list)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
