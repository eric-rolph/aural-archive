"""
Aural Archive — Digital Repository Extractor
============================================
Handles archival capture from online repositories and any other 
yt-dlp-supported site.
"""

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .. import config
from ..headers import get_random_headers
from ..utils import sanitize_filename
from .base import BaseExtractor


class YouTubeExtractor(BaseExtractor):
    """Extractor for YouTube and all yt-dlp-supported sites."""

    name = "youtube"

    _URL_PATTERNS = [
        re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/watch"),
        re.compile(r"(?:https?://)?youtu\.be/"),
        re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/shorts/"),
        re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/playlist"),
        re.compile(r"(?:https?://)?(?:music\.)?youtube\.com/"),
    ]

    def extract_info(self, url: str) -> dict:
        """Fetch video metadata via yt-dlp --dump-json."""
        yt_dlp = config.get_yt_dlp()
        headers = get_random_headers()

        cmd = [
            yt_dlp,
            "--dump-json",
            "--no-download",
            "--no-playlist",
            "--user-agent", headers["User-Agent"],
            url,
        ]
        for key, val in headers.items():
            if key != "User-Agent":
                cmd.extend(["--add-header", f"{key}:{val}"])

        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

        if result.returncode != 0:
            return {}

        try:
            data = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            return {}

        return {
            "id": data.get("id", ""),
            "title": data.get("title", "Unknown"),
            "url": data.get("webpage_url") or url,
            "duration": data.get("duration") or 0,
            "channel": data.get("channel") or data.get("uploader") or "Unknown",
            "description": data.get("description") or "",
            "tags": data.get("tags") or [],
            "upload_date": data.get("upload_date") or "",
            "thumbnail": data.get("thumbnail") or "",
        }

    def download(
        self,
        url: str,
        output_dir: Path,
        sample_rate: int = 44100,
        bit_depth: int = 16,
        output_format: str = "wav",
        title_hint: str = "",
        extra_args: list[str] | None = None,
    ) -> dict | None:
        """
        Acquire audio via yt-dlp, convert to target format with ffmpeg.
        Also writes a .info.json sidecar via yt-dlp's built-in flag.
        """
        yt_dlp = config.get_yt_dlp()
        ffmpeg = config.get_ffmpeg()
        headers = get_random_headers()

        # Step 1: Download best audio with yt-dlp
        tmp_template = str(output_dir / "%(title)s.%(ext)s")
        cmd_dl = [
            yt_dlp,
            "--no-playlist",
            "-x",                          # extract audio
            "--audio-format", "wav",
            "--ffmpeg-location", str(Path(ffmpeg).parent),
            "-o", tmp_template,
            "--no-overwrites",
            "--write-info-json",           # generate sidecar metadata
            "--user-agent", headers["User-Agent"],
            url,
        ]
        # Add rotated headers
        for key, val in headers.items():
            if key != "User-Agent":
                cmd_dl.extend(["--add-header", f"{key}:{val}"])

        if extra_args:
            cmd_dl.extend(extra_args)

        print(f"  ⬇  Acquiring: {url}")
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
                "--write-info-json",
                "--user-agent", headers["User-Agent"],
                url,
            ]
            for key, val in headers.items():
                if key != "User-Agent":
                    cmd_dl_fb.extend(["--add-header", f"{key}:{val}"])

            dl_result = subprocess.run(cmd_dl_fb, capture_output=True, text=True, encoding="utf-8")
            if dl_result.returncode != 0:
                print(f"  ✗  Download FAILED for: {url}")
                print(f"     stderr: {dl_result.stderr[:300]}")
                return None

        # Find the archived file (most recent non-JSON file in output_dir)
        downloaded_file = self._find_latest_file(output_dir)
        if not downloaded_file:
            print(f"  ✗  Could not find archived file in {output_dir}")
            return None

        print(f"  ✓  Archived: {downloaded_file.name}")

        # Step 2: Convert to target format with precise specs via ffmpeg
        out_name = sanitize_filename(downloaded_file.stem) + f".{output_format}"
        out_path = output_dir / out_name

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
            "-ac", "2",
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
        duration = self._get_duration(out_path)
        print(f"  ✓  Output: {out_path.name}  ({duration:.1f}s)")

        # Generate merged sidecar
        from ..sidecar import generate_sidecar
        sidecar_info = {
            "source_url": url,
            "title": title_hint or out_path.stem,
            "extractor": self.name,
            "format": output_format,
            "sample_rate": sample_rate,
            "bit_depth": bit_depth,
        }
        # Merge with any yt-dlp .info.json that was written
        ytdlp_info_file = self._find_info_json(output_dir, out_path.stem)
        if ytdlp_info_file:
            sidecar_info["_ytdlp_info_file"] = str(ytdlp_info_file)
        sidecar_path = generate_sidecar(out_path, sidecar_info, ytdlp_info_file)

        return {
            "file": str(out_path.name),
            "source_url": url,
            "title": title_hint or out_path.stem,
            "duration_seconds": round(duration, 2),
            "sample_rate": sample_rate,
            "bit_depth": bit_depth,
            "format": output_format,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "extractor": self.name,
            "sidecar": str(out_path.with_suffix(".info.json").name),
        }

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _find_latest_file(directory: Path) -> Path | None:
        """Find the most recently modified non-JSON file in directory."""
        files = [
            f for f in directory.iterdir()
            if f.is_file() and f.suffix.lower() not in {".json", ".db"}
        ]
        if not files:
            return None
        return max(files, key=lambda f: f.stat().st_mtime)

    @staticmethod
    def _find_info_json(directory: Path, stem: str) -> Path | None:
        """Find a yt-dlp .info.json file matching the given stem."""
        # yt-dlp writes <title>.info.json
        candidates = list(directory.glob("*.info.json"))
        if not candidates:
            return None
        # Try to match by stem similarity, or just return the most recent
        for c in candidates:
            # yt-dlp names it <title>.info.json, so strip .info.json
            if c.stem.replace(".info", "") in stem or stem in c.stem:
                return c
        # Fallback: most recent .info.json
        return max(candidates, key=lambda f: f.stat().st_mtime)

    @staticmethod
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
