"""
Aural Archive — Sample Extraction Module
==========================================
Extracts timestamped clips from downloaded audio files based on
an extraction map (extractions.json). Outputs organized clips
ready for DAW arrangement.

Generalized from extract_samples.py in the auction-audio-pipeline.
"""

import json
import subprocess
from pathlib import Path

from . import config
from .utils import sanitize_filename


def load_extractions(project: str) -> dict:
    """Load the extraction map from the project's extractions.json."""
    extractions_file = config.get_project_extractions_file(project)
    if not extractions_file.exists():
        print(f"ERROR: No extractions.json found at {extractions_file}")
        print(f"Create one to define which clips to extract.")
        print(f"See projects/_example_song/extractions.json for format.")
        return {}
    with open(extractions_file, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_clip(source_path: Path, start: float, end: float,
                 output_path: Path, sample_rate: int = 44100,
                 bit_depth: int = 16) -> bool:
    """Extract a clip using ffmpeg."""
    ffmpeg = config.get_ffmpeg()
    duration = end - start

    codec_map = {16: "pcm_s16le", 24: "pcm_s24le", 32: "pcm_s32le"}
    codec = codec_map.get(bit_depth, "pcm_s16le")

    cmd = [
        ffmpeg, "-y",
        "-ss", f"{start:.3f}",
        "-i", str(source_path),
        "-t", f"{duration:.3f}",
        "-acodec", codec,
        "-ar", str(sample_rate),
        "-ac", "2",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ✗  FAILED: {output_path.name}")
        print(f"     {result.stderr[:200]}")
        return False
    return True


def run_extraction(project: str, sample_rate: int = 44100, bit_depth: int = 16):
    """Run the full extraction pipeline for a project."""
    extractions = load_extractions(project)
    if not extractions:
        return

    output_dir = config.get_project_output_dir(project)
    samples_dir = config.get_project_samples_dir(project)

    print("=" * 70)
    print(f"  Aural Archive — SAMPLE EXTRACTION")
    print(f"  Project: {project}")
    print("=" * 70)

    total_clips = 0
    success_clips = 0
    manifest = {}

    for category, sources in extractions.items():
        cat_dir = samples_dir / category
        cat_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'═' * 70}")
        print(f"  {category}")
        print(f"{'═' * 70}")

        for source_entry in sources:
            source_rel = source_entry["source"]
            source_path = output_dir / source_rel

            if not source_path.exists():
                print(f"  ⚠  Source not found: {source_rel}")
                continue

            for clip in source_entry["clips"]:
                total_clips += 1
                clip_name = clip["name"]
                output_path = cat_dir / f"{clip_name}.wav"

                print(f"  ⚙  [{clip['start']:.1f}s → {clip['end']:.1f}s]  {clip_name}")
                if clip.get("note"):
                    print(f"      Note: {clip['note'][:80]}")

                if extract_clip(source_path, clip["start"], clip["end"],
                               output_path, sample_rate, bit_depth):
                    success_clips += 1
                    size_kb = output_path.stat().st_size / 1024
                    duration = clip["end"] - clip["start"]
                    print(f"  ✓  {output_path.name}  ({duration:.1f}s, {size_kb:.0f} KB)")

                    manifest[clip_name] = {
                        "file": str(output_path.relative_to(samples_dir)),
                        "source": source_rel,
                        "start": clip["start"],
                        "end": clip["end"],
                        "duration": round(duration, 2),
                        "note": clip.get("note", ""),
                        "category": category,
                    }

    # Save manifest
    manifest_path = samples_dir / "samples_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n{'═' * 70}")
    print(f"  EXTRACTION COMPLETE")
    print(f"  Success: {success_clips}/{total_clips} clips")
    print(f"  Output: {samples_dir}")
    print(f"  Manifest: {manifest_path}")
    print(f"{'═' * 70}")

    # Print summary by category
    print(f"\n  Category breakdown:")
    for cat in extractions:
        cat_dir = samples_dir / cat
        wavs = list(cat_dir.glob("*.wav")) if cat_dir.exists() else []
        total_size = sum(w.stat().st_size for w in wavs) / (1024 * 1024)
        print(f"    {cat}: {len(wavs)} clips ({total_size:.1f} MB)")
