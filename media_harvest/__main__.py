"""
Aural Archive — Unified CLI
============================
Entry point for all aural-archive operations.

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
from .state import StateManager


SPLASH = r"""
 _______  __   __  ______    _______  ___        _______  ______    _______  __   __  ___   __   __  _______ 
|   _   ||  | |  ||    _ |  |   _   ||   |      |   _   ||    _ |  |       ||  | |  ||   | |  | |  ||       |
|  |_|  ||  | |  ||   | ||  |  |_|  ||   |      |  |_|  ||   | ||  |       ||  |_|  ||   | |  |_|  ||    ___|
|       ||  |_|  ||   |_||_ |       ||   |      |       ||   |_||_ |       ||       ||   | |       ||   |___ 
|       ||       ||    __  ||       ||   |___   |       ||    __  ||      _||       ||   | |       ||    ___|
|   _   ||       ||   |  | ||   _   ||       |  |   _   ||   |  | ||     |_ |   _   ||   |  |     | |   |___ 
|__| |__||_______||___|  |_||__| |__||_______|  |__| |__||___|  |_||_______||__| |__||___|   |___|  |_______|

              SONIC ARCHIVAL & TRANSCRIPTION TOOLKIT
"""


# ─────────────────────────────────────────────────────────────────────────────
# Init command
# ─────────────────────────────────────────────────────────────────────────────

EXAMPLE_PRESETS = {
    "categories": {
        "01_field_recordings": {
            "label": "Field Recordings",
            "description": "Environmental audio, site recordings, and found sound.",
            "search_terms": [
                "field recording nature",
                "urban ambient atmosphere"
            ],
            "keywords": ["ambient", "field", "atmosphere"]
        },
        "02_archival_sources": {
            "label": "Archival Sources",
            "description": "Historical broadcasts, oral histories, and public domain archives.",
            "search_terms": [
                "archival interview audio",
                "historical radio broadcast"
            ],
            "keywords": ["archive", "history", "speech"]
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
    print(f"     ├── presets.json       ← Edit: define archival acquisition parameters")
    print(f"     ├── extractions.json   ← Edit: define which clips to cut (after analysis)")
    print(f"     ├── output/            ← Archived recordings land here")
    print(f"     └── samples/           ← Extracted clips land here")
    print(f"\n  Next steps (Research Workflow):")
    print(f"     1. Edit presets.json with your target parameters")
    print(f"     2. python -m media_harvest capture --project {project} --search")
    print(f"     3. python -m media_harvest transcribe --project {project}")
    print(f"     4. python -m media_harvest view --project {project} --num 1")
    print(f"     5. Edit extractions.json with timestamps for curated samples")
    print(f"     6. python -m media_harvest extract --project {project}")
    print(f"     7. python -m media_harvest stats --project {project}")


# ─────────────────────────────────────────────────────────────────────────────
# Download command
# ─────────────────────────────────────────────────────────────────────────────

def cmd_download(args):
    """Acquire audio from digital repositories."""
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
    print(f"  AURAL ARCHIVE — ACQUIRE")
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
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    console = Console()

    project = args.project
    project_dir = config.get_project_dir(project)

    if not project_dir.exists():
        console.print(f"\n  [red]✗[/] Project '{project}' not found.")
        return

    console.print(Panel(f"[bold blue]PROJECT ANALYSIS:[/] [green]{project}[/]", expand=False))

    # Presets
    presets_file = config.get_project_presets_file(project)
    if presets_file.exists():
        with open(presets_file, "r", encoding="utf-8") as f:
            presets = json.load(f)
        cats = presets.get("categories", {})
        console.print(f"\n  [bold]📋 Categories:[/] {len(cats)}")
        for cat_id, cat in cats.items():
            terms = len(cat.get("search_terms", []))
            console.print(f"     • [cyan]{cat_id}[/]: {cat.get('label', '')} ({terms} terms)")
    else:
        console.print(f"\n  [yellow]⚠[/] No [dim]presets.json[/] found")

    # Capture Stats
    output_dir = config.get_project_output_dir(project)
    manifest = load_manifest(project)
    console.print(f"\n  [bold]⬇  Archived Files:[/] {len(manifest)}")
    
    if output_dir.exists():
        cat_table = Table(box=None, show_header=False)
        for cat_dir in sorted(output_dir.iterdir()):
            if cat_dir.is_dir():
                audio_files = [f for f in cat_dir.iterdir()
                              if f.is_file() and f.suffix.lower() in {".wav", ".mp3", ".flac"}]
                if audio_files:
                    total_mb = sum(f.stat().st_size for f in audio_files) / (1024 * 1024)
                    cat_table.add_row(f"     • [cyan]{cat_dir.name}[/]:", f"{len(audio_files)} files", f"({total_mb:.1f} MB)")
        if cat_table.row_count:
            console.print(cat_table)

    # Transcripts
    transcripts = load_transcripts(project)
    console.print(f"\n  [bold]🎙  Transcripts:[/] {len(transcripts)} files")

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
        console.print(f"\n  [bold]✂️  Extraction Map:[/] {len(extractions)} categories, [green]{total_clips}[/] clips defined")
    else:
        console.print(f"\n  [bold]✂️  Extraction Map:[/] [dim]No extractions.json yet[/]")

    # Samples
    samples_dir = config.get_project_samples_dir(project)
    if samples_dir.exists():
        sample_wavs = list(samples_dir.rglob("*.wav"))
        if sample_wavs:
            total_mb = sum(f.stat().st_size for f in sample_wavs) / (1024 * 1024)
            console.print(f"\n  [bold]🎵  Curated Samples:[/] [green]{len(sample_wavs)}[/] clips ({total_mb:.1f} MB)")
        else:
            console.print(f"\n  [bold]🎵  Curated Samples:[/] [dim]none extracted yet[/]")

    # Archival Milestones (Whimsy Injector)
    from rich.emoji import Emoji
    milestones = []
    if len(manifest) >= 1: milestones.append("Preservation Started 🏺")
    if len(transcripts) >= 1: milestones.append("Voices Documented 📜")
    if len(extractions_file.exists() and extractions_file.stat().st_size > 100): milestones.append("Knowledge Synthesized 🧠")
    
    if milestones:
        console.print(f"\n  [bold magenta]✨ ARCHIVAL MILESTONES:[/]")
        for m in milestones:
            console.print(f"     [bold reverse white]  [/] [italic]{m}[/]")

    print()


# ─────────────────────────────────────────────────────────────────────────────
# Journal command
# ─────────────────────────────────────────────────────────────────────────────

def cmd_journal(args):
    """Inspect and manage the acquisition journal."""
    from rich.console import Console
    from rich.table import Table
    console = Console()

    project = args.project
    with StateManager(project) as state:
        if args.retry_failed:
            state.reset_failed()
            console.print(f"\n  [bold green]✓[/] Reset all [red]failed[/] jobs to [yellow]pending[/].\n")
            return

        jobs = state.get_all()
        if not jobs:
            console.print(f"\n  [yellow]⚠[/] Journal is empty for project '{project}'.")
            return

        table = Table(title=f"Acquisition Journal: {project}")
        table.add_column("Status", style="bold")
        table.add_column("Title")
        table.add_column("Category")
        table.add_column("Extractor")
        table.add_column("Details")

        for j in jobs:
            status_map = {
                "completed": "[green]COMPLETED[/]",
                "failed": "[red]FAILED[/]",
                "in_progress": "[yellow]IN_PROGRESS[/]",
                "pending": "[dim]PENDING[/]"
            }
            status = status_map.get(j["status"], j["status"])
            details = j["result_file"] if j["status"] == "completed" else (j["error"] or "")
            table.add_row(
                status,
                j["title"] or "Unknown",
                j["category"] or "",
                j["extractor"] or "",
                details
            )

        console.print(table)
        counts = state.get_counts()
        console.print(f"\n  [bold]Summary:[/] {counts.get('completed', 0)} done, "
                      f"{counts.get('failed', 0)} failed, "
                      f"{counts.get('pending', 0)} pending\n")


def cmd_view(args):
    """View a transcript in the terminal."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    console = Console()

    project = args.project
    transcripts = load_transcripts(project)

    if not transcripts:
        console.print(f"\n  [yellow]⚠[/] No transcripts found for project '{project}'. Run 'transcribe' first.")
        return

    # If no file specified, list available ones
    if not args.file and not args.num:
        table = Table(title=f"Transcripts: {project}")
        table.add_column("#", justify="right", style="dim")
        table.add_column("File")
        table.add_column("Lang")
        table.add_column("Segments")

        for i, (rel_path, data) in enumerate(transcripts.items(), 1):
            table.add_row(
                str(i),
                rel_path,
                data.get("language", "??"),
                str(data.get("segment_count", 0))
            )
        console.print(table)
        console.print("\n  [dim]Use --file <path> or --num <index> to view a specific transcript.[/]")
        return

    # Find the target transcript
    target = None
    path = ""
    if args.file:
        target = transcripts.get(args.file)
        path = args.file
    elif args.num:
        idx = int(args.num) - 1
        keys = list(transcripts.keys())
        if 0 <= idx < len(keys):
            path = keys[idx]
            target = transcripts[path]

    if not target:
        console.print(f"\n  [red]✗[/] Transcript not found.")
        return

    # Search for the .txt file on disk
    txt_path = config.get_project_output_dir(project) / Path(path).with_suffix(".txt")

    if txt_path.exists():
        with open(txt_path, "r", encoding="utf-8") as f:
            content = f.read()

        console.print(Panel(f"[bold green]TRANSCRIPT:[/] {path}", expand=False))
        console.print(content)
        
        # Show metadata if requested
        if args.meta:
            meta_path = config.get_project_output_dir(project) / Path(path).with_suffix(".info.json")
            if meta_path.exists():
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta_data = json.load(f)
                from rich.syntax import Syntax
                console.print(Panel("[bold cyan]ARCHIVAL CONTEXT (Sidecar):[/]", expand=False))
                console.print(Syntax(json.dumps(meta_data, indent=2), "json", theme="monokai"))
            else:
                # Try finding it in category subfolder
                for cat in config.get_project_output_dir(project).iterdir():
                    if cat.is_dir():
                        c_path = cat / Path(path).with_suffix(".info.json")
                        if c_path.exists():
                            with open(c_path, "r", encoding="utf-8") as f:
                                meta_data = json.load(f)
                            from rich.syntax import Syntax
                            console.print(Panel("[bold cyan]ARCHIVAL CONTEXT (Sidecar):[/]", expand=False))
                            console.print(Syntax(json.dumps(meta_data, indent=2), "json", theme="monokai"))
                            break
    else:
        console.print(Panel(f"[bold green]TRANSCRIPT (Manifest Only):[/] {path}", expand=False))
        console.print(target.get("text", "(no text)"))


def cmd_stats(args):
    """Show detailed archival metrics for a project."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    console = Console()

    project = args.project
    manifest = load_manifest(project)
    transcripts = load_transcripts(project)

    if not manifest:
        console.print(f"\n  [yellow]⚠[/] No archival data found for project '{project}'.")
        return

    total_size_bytes = 0
    total_duration_sec = 0
    extractors = {}
    languages = {}

    for m in manifest:
        total_duration_sec += m.get("duration_seconds", 0)
        ext = m.get("extractor", "unknown")
        extractors[ext] = extractors.get(ext, 0) + 1

        # Calculate size from disk (check output/ and subdirs)
        output_dir = config.get_project_output_dir(project)
        rel_path = m.get("file", "")
        path = output_dir / rel_path
        
        if not path.exists() and m.get("category"):
            path = output_dir / m["category"] / rel_path

        if path.exists():
            total_size_bytes += path.stat().st_size

    for t in transcripts.values():
        lang = t.get("language", "unknown")
        languages[lang] = languages.get(lang, 0) + 1

    console.print(Panel(f"[bold magenta]ARCHIVAL METRICS:[/] {project}", expand=False))

    # Overview Table
    ov_table = Table(box=None)
    ov_table.add_column("Metric", style="bold cyan")
    ov_table.add_column("Value")

    from .utils import format_duration
    ov_table.add_row("Total Preservation Time:", format_duration(total_duration_sec))
    ov_table.add_row("Total Storage Occupied:", f"{total_size_bytes / (1024**3):.2f} GB")
    ov_table.add_row("Captured Artifacts:", f"{len(manifest)}")
    ov_table.add_row("Transcribed Artifacts:", f"{len(transcripts)}")
    console.print(ov_table)

    # Archival Levels (Whimsy Injector)
    lvl = "Novice Archivist"
    if total_duration_sec > 3600: lvl = "Sonic Researcher"
    if total_duration_sec > 36000: lvl = "Master Preserver"
    if total_duration_sec > 360000: lvl = "Guardian of Sound"
    
    console.print(f"  [bold magenta]LEVEL:[/] [italic underline]{lvl}[/]\n")

    # Breakdown Tables
    col1, col2 = Table(box=None), Table(box=None)
    col1.add_column("Source Repositories", style="bold")
    col2.add_column("Linguistic Diversity", style="bold")

    for ext, count in sorted(extractors.items(), key=lambda x: x[1], reverse=True):
        col1.add_row(f"{ext.capitalize()}", f"{count}")

    for lang, count in sorted(languages.items(), key=lambda x: x[1], reverse=True):
        col2.add_row(f"{lang.upper()}", f"{count}")

    from rich.columns import Columns
    console.print(Columns([col1, col2]))
    console.print()


def cmd_doctor(args):
    """Check health of the archival environment."""
    from rich.console import Console
    from rich.table import Table
    console = Console()

    table = Table(title="Aural Archive — Environment Health Check")
    table.add_column("Component", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Path / Details", style="dim")

    # 1. FFmpeg
    ffmpeg = config.get_ffmpeg()
    if ffmpeg and Path(ffmpeg).exists():
        table.add_row("FFmpeg", "[green]✓ READY[/]", ffmpeg)
    else:
        table.add_row("FFmpeg", "[red]✗ MISSING[/]", "Required for audio conversion")

    # 2. yt-dlp
    ytdlp = config.get_yt_dlp()
    if ytdlp and Path(ytdlp).exists():
        table.add_row("yt-dlp", "[green]✓ READY[/]", ytdlp)
    else:
        table.add_row("yt-dlp", "[red]✗ MISSING[/]", "Required for acquisition")

    # 3. Gemini API
    import os
    from dotenv import load_dotenv
    load_dotenv()
    if os.getenv("GEMINI_API_KEY"):
        table.add_row("Gemini API", "[green]✓ LINKED[/]", "KEY FOUND (.env)")
    else:
        table.add_row("Gemini API", "[yellow]⚠ OPTIONAL[/]", "Missing (Required for Vision Transcripts)")

    # 4. Whisper
    try:
        import whisper
        table.add_row("Whisper", "[green]✓ INSTALLED[/]", "Ready for local transcription")
    except ImportError:
        table.add_row("Whisper", "[red]✗ MISSING[/]", "Run 'pip install openai-whisper'")

    console.print()
    console.print(table)
    console.print("\n  [dim]Check README for setup instructions if components are missing.[/]\n")


# ─────────────────────────────────────────────────────────────────────────────
# List command
# ─────────────────────────────────────────────────────────────────────────────

def cmd_list(args):
    """List all projects."""
    from rich.console import Console
    from rich.table import Table
    console = Console()

    projects_dir = config.PROJECTS_DIR
    console.print(f"\n  [bold blue]Aural Archive[/] — [dim]Archival Projects[/]")

    if not projects_dir.exists():
        console.print("  [yellow]⚠[/] No projects found. Create one with: [cyan]python -m media_harvest init <name>[/]")
        return

    table = Table(box=None, show_header=False)
    found = False
    for p in sorted(projects_dir.iterdir()):
        if p.is_dir() and not p.name.startswith(".") and not p.name.startswith("_"):
            found = True
            manifest = []
            manifest_file = p / "output" / "manifest.json"
            if manifest_file.exists():
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            table.add_row(f"  • [cyan]{p.name}[/]", f"({len(manifest)} captures)")

    if found:
        console.print(table)
    else:
        console.print("  [yellow]⚠[/] No projects found.")

    console.print()


# ─────────────────────────────────────────────────────────────────────────────
# Main parser
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="aural_archive",
        description="Aural Archive: Sonic Archival & Transcription Toolkit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python -m media_harvest init field-study-01
  python -m media_harvest capture --project field-study-01 --search
  python -m media_harvest capture --project field-study-01 --url "https://..."
  python -m media_harvest transcribe --project field-study-01
  python -m media_harvest view --project field-study-01 --num 1
  python -m media_harvest stats --project field-study-01
  python -m media_harvest list
        """,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── init ──
    p_init = subparsers.add_parser("init", help="Initialize a new project")
    p_init.add_argument("project_name", help="Name for the new project")
    p_init.set_defaults(func=cmd_init)

    # ── capture ──
    p_dl = subparsers.add_parser("capture", help="Acquire audio from digital repositories or local sources")
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

    # ── download (legacy alias) ──
    p_dl_leg = subparsers.add_parser("download", help="Alias for 'capture'")
    p_dl_leg.add_argument("--project", "-p", required=True, help="Project name")
    mode_group_leg = p_dl_leg.add_mutually_exclusive_group(required=True)
    mode_group_leg.add_argument("--search", action="store_true")
    mode_group_leg.add_argument("--batch", action="store_true")
    mode_group_leg.add_argument("--url", type=str)
    p_dl_leg.add_argument("--category", "-c")
    p_dl_leg.add_argument("--max-results", type=int, default=5)
    p_dl_leg.add_argument("--max-duration", type=int, default=600)
    p_dl_leg.add_argument("--sample-rate", type=int, default=44100)
    p_dl_leg.add_argument("--bit-depth", type=int, choices=[16, 24, 32], default=16)
    p_dl_leg.add_argument("--output-format", default="wav")
    p_dl_leg.add_argument("--dry-run", action="store_true")
    p_dl_leg.set_defaults(func=cmd_download)

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

    # ── journal ──
    p_jo = subparsers.add_parser("journal", help="Inspect and manage acquisition state")
    p_jo.add_argument("--project", "-p", required=True, help="Project name")
    p_jo.add_argument("--retry-failed", action="store_true", help="Reset failed jobs to pending")
    p_jo.set_defaults(func=cmd_journal)

    # ── view ──
    p_v = subparsers.add_parser("view", help="View a transcript in the terminal")
    p_v.add_argument("--project", "-p", required=True, help="Project name")
    p_v.add_argument("--file", "-f", help="Relative path to audio file")
    p_v.add_argument("--num", "-n", help="Index of transcript to view")
    p_v.add_argument("--meta", action="store_true", help="Show sidecar metadata context")
    p_v.set_defaults(func=cmd_view)

    # ── stats ──
    p_stat = subparsers.add_parser("stats", help="Show detailed archival metrics")
    p_stat.add_argument("--project", "-p", required=True, help="Project name")
    p_stat.set_defaults(func=cmd_stats)

    # ── doctor ──
    p_doc = subparsers.add_parser("doctor", help="Check health of the environment")
    p_doc.set_defaults(func=cmd_doctor)

    # ── list ──
    p_ls = subparsers.add_parser("list", help="List all projects")
    p_ls.set_defaults(func=cmd_list)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Global Disclaimer & Splash
    print(SPLASH)
    print(f"{'─' * 70}")
    print("  NOTICE: Aural Archive is for personal and research use with content")
    print("  you have the legal right to access. Respect all copyrights.")
    print(f"{'─' * 70}")

    args.func(args)


if __name__ == "__main__":
    main()
