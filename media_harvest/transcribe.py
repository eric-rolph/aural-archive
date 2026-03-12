"""
Media Harvest — Transcription Module
======================================
Transcribes downloaded audio files using multiple strategies:
  1. YouTube captions API (fastest, if available)
  2. OpenAI Whisper (local, robust fallback)
  3. Google Gemini visual transcription (for video with scene descriptions)

Generalized from transcribe-suite and auction-audio-pipeline.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .utils import get_video_id

# Lazy imports — these are heavy dependencies
_whisper = None
_genai = None
_yt_transcript_api = None


def _get_whisper():
    global _whisper
    if _whisper is None:
        try:
            import whisper
            _whisper = whisper
        except ImportError:
            print("ERROR: openai-whisper not installed.")
            print("  pip install openai-whisper")
            sys.exit(1)
    return _whisper


def _get_genai():
    global _genai
    if _genai is None:
        try:
            import google.generativeai as genai
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                print("ERROR: GEMINI_API_KEY not set in .env")
                sys.exit(1)
            genai.configure(api_key=api_key)
            _genai = genai
        except ImportError:
            print("ERROR: google-generativeai not installed.")
            print("  pip install google-generativeai")
            sys.exit(1)
    return _genai


def _get_youtube_transcript_api():
    global _yt_transcript_api
    if _yt_transcript_api is None:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            _yt_transcript_api = YouTubeTranscriptApi
        except ImportError:
            _yt_transcript_api = False  # Mark as unavailable, not None
    return _yt_transcript_api if _yt_transcript_api is not False else None


# ─────────────────────────────────────────────────────────────────────────────
# Transcription strategies
# ─────────────────────────────────────────────────────────────────────────────

def transcribe_from_captions(url: str) -> str | None:
    """Attempt to fetch YouTube captions via the transcript API."""
    api = _get_youtube_transcript_api()
    if not api:
        return None

    video_id = get_video_id(url)
    if not video_id:
        return None

    try:
        transcript_list = api.list_transcripts(video_id)
        try:
            transcript = transcript_list.find_transcript(["en"])
        except Exception:
            try:
                transcript = transcript_list.find_generated_transcript(["en"])
            except Exception:
                return None

        result = transcript.fetch()
        return " ".join(line["text"] for line in result)
    except Exception:
        return None


def transcribe_with_whisper(audio_path: str, model_size: str = "base") -> dict:
    """Transcribe an audio file using local Whisper model."""
    whisper = _get_whisper()

    # Ensure ffmpeg is on PATH for Whisper
    ffmpeg_dir = str(Path(config.get_ffmpeg()).parent)
    os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

    print(f"  🎙  Transcribing: {Path(audio_path).name}")
    start = time.time()

    model = whisper.load_model(model_size)
    result = model.transcribe(str(audio_path), verbose=False)

    elapsed = time.time() - start
    text = result["text"].strip()
    language = result.get("language", "unknown")

    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "start": round(seg["start"], 2),
            "end": round(seg["end"], 2),
            "text": seg["text"].strip(),
        })

    print(f"  ✓  Done ({elapsed:.1f}s) — {len(text)} chars, language: {language}")
    if text:
        preview = text[:120] + ("..." if len(text) > 120 else "")
        print(f'     Preview: "{preview}"')

    return {
        "text": text,
        "language": language,
        "segments": segments,
        "processing_seconds": round(elapsed, 2),
    }


def transcribe_video_visual(video_path: str) -> str:
    """Upload video to Gemini and generate a visual/script-style transcript."""
    genai = _get_genai()

    print(f"  📹  Uploading video to Gemini: {video_path}...")
    video_file = genai.upload_file(path=video_path, mime_type="video/mp4")
    print(f"  File uploaded: {video_file.name}")

    # Wait for processing
    while video_file.state.name == "PROCESSING":
        print(".", end="", flush=True)
        time.sleep(2)
        video_file = genai.get_file(video_file.name)

    if video_file.state.name == "FAILED":
        raise Exception("Video processing failed.")

    print("\n  Generating visual transcript...")
    model = genai.GenerativeModel(model_name="gemini-flash-latest")

    prompt = (
        "Watch this video and create a detailed transcript. "
        "Format it like a movie script. "
        "Include visual scene descriptions (scene headings, action lines) "
        "describing the setting, characters, and actions. "
        "Interleave the spoken dialogue with these visual descriptions clearly. "
        "Use timestamps for major scene changes if possible."
    )

    response = model.generate_content([video_file, prompt])
    return response.text


# ─────────────────────────────────────────────────────────────────────────────
# Batch transcription
# ─────────────────────────────────────────────────────────────────────────────

def load_transcripts(project: str) -> dict:
    transcripts_file = config.get_project_transcripts_file(project)
    if transcripts_file.exists():
        with open(transcripts_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_transcripts(project: str, data: dict):
    transcripts_file = config.get_project_transcripts_file(project)
    transcripts_file.parent.mkdir(parents=True, exist_ok=True)
    with open(transcripts_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def collect_audio_files(project: str, category: str | None = None) -> list[Path]:
    """Collect all audio files in the project's output directory."""
    output_dir = config.get_project_output_dir(project)
    audio_extensions = {".wav", ".mp3", ".flac", ".m4a", ".opus", ".ogg"}

    if not output_dir.exists():
        return []

    if category:
        cat_dir = output_dir / category
        if cat_dir.exists():
            return sorted(f for f in cat_dir.iterdir()
                         if f.is_file() and f.suffix.lower() in audio_extensions)
        return []

    files = []
    for cat_dir in sorted(output_dir.iterdir()):
        if cat_dir.is_dir():
            files.extend(sorted(
                f for f in cat_dir.iterdir()
                if f.is_file() and f.suffix.lower() in audio_extensions
            ))
    return files


def batch_transcribe(project: str, model_size: str = "base",
                     category: str | None = None, force: bool = False):
    """Transcribe all audio files in a project using Whisper."""
    audio_files = collect_audio_files(project, category)
    if not audio_files:
        print("No audio files found. Run 'download' first.")
        return

    output_dir = config.get_project_output_dir(project)

    print("=" * 70)
    print(f"  MEDIA HARVEST — TRANSCRIPTION")
    print(f"  Project: {project}")
    print(f"  Model: whisper-{model_size}  |  Files: {len(audio_files)}")
    print("=" * 70)

    # Load Whisper model once
    whisper = _get_whisper()
    print(f"\n  Loading Whisper '{model_size}' model...")

    # Ensure ffmpeg is on PATH
    ffmpeg_dir = str(Path(config.get_ffmpeg()).parent)
    os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

    model = whisper.load_model(model_size)
    print(f"  ✓  Model loaded.\n")

    transcripts = load_transcripts(project)
    total_start = time.time()
    processed = 0
    skipped = 0

    for audio_path in audio_files:
        rel_path = str(audio_path.relative_to(output_dir))
        txt_path = audio_path.with_suffix(".txt")
        category_name = audio_path.parent.name

        # Skip if already transcribed (unless --force)
        if not force and rel_path in transcripts:
            print(f"  ⏭  Skipping (already done): {audio_path.name}")
            skipped += 1
            continue

        # Transcribe
        print(f"  🎙  Transcribing: {audio_path.name}")
        start = time.time()
        result = model.transcribe(str(audio_path), verbose=False)
        elapsed = time.time() - start

        text = result["text"].strip()
        language = result.get("language", "unknown")
        segments = []
        for seg in result.get("segments", []):
            segments.append({
                "start": round(seg["start"], 2),
                "end": round(seg["end"], 2),
                "text": seg["text"].strip(),
            })

        print(f"  ✓  Done ({elapsed:.1f}s) — {len(text)} chars, language: {language}")
        if text:
            preview = text[:120] + ("..." if len(text) > 120 else "")
            print(f'     Preview: "{preview}"')

        # Save individual .txt transcript next to the audio file
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"# Transcript: {audio_path.stem}\n")
            f.write(f"# Category: {category_name}\n")
            f.write(f"# Model: whisper-{model_size}\n")
            f.write(f"# Language: {language}\n")
            f.write(f"# Generated: {datetime.now(timezone.utc).isoformat()}\n\n")
            f.write(text)
            f.write("\n\n# --- Timestamped Segments ---\n\n")
            for seg in segments:
                f.write(f"[{seg['start']:.2f} → {seg['end']:.2f}]  {seg['text']}\n")

        # Update combined manifest
        transcripts[rel_path] = {
            "file": rel_path,
            "category": category_name,
            "text": text,
            "language": language,
            "segment_count": len(segments),
            "whisper_model": model_size,
            "transcribed_at": datetime.now(timezone.utc).isoformat(),
        }
        save_transcripts(project, transcripts)
        processed += 1
        print()

    total_elapsed = time.time() - total_start

    print("=" * 70)
    print(f"  TRANSCRIPTION COMPLETE")
    print(f"  Processed: {processed}  |  Skipped: {skipped}  |  Total time: {total_elapsed:.0f}s")
    print(f"  Individual transcripts: .txt files alongside each audio file")
    print(f"  Combined manifest: {config.get_project_transcripts_file(project)}")
    print("=" * 70)
