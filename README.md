# 🎵 Media Harvest

**A general-purpose media extraction & transcription toolkit.**

Download audio from YouTube (or any yt-dlp-supported site), transcribe it with Whisper or captions API, and extract timestamped samples — all organized into named projects for any creative need: songs, documentaries, podcasts, sample packs, whatever.

## Features

- **🔍 Smart Search** — Search YouTube with preset queries, browse results interactively, or batch-download
- **⬇️ Download & Convert** — Extract audio and convert to production-ready WAV (PCM 16/24/32-bit, configurable sample rate)
- **🎙️ Multi-Strategy Transcription**:
  - **YouTube Captions API** — fastest, pulls official/auto-generated captions
  - **OpenAI Whisper** — local speech-to-text with timestamped segments
  - **Google Gemini** — visual video transcription with scene descriptions
- **✂️ Sample Extraction** — Cut precise clips by timestamp from downloaded files
- **📁 Project-Based Organization** — Each creative project gets its own config, downloads, transcripts, and samples

## Quick Start

### 1. Setup

```powershell
git clone https://github.com/eric-rolph/media-harvest.git
cd media-harvest
.\setup.ps1
.\venv\Scripts\Activate.ps1
```

### 2. Create a Project

```powershell
python -m media_harvest init my-song
```

This creates `projects/my-song/` with template config files.

### 3. Configure Search Presets

Edit `projects/my-song/presets.json` to define your categories and YouTube search terms:

```json
{
  "categories": {
    "01_vocals": {
      "label": "Vocals & Speech",
      "description": "Spoken word samples for the intro.",
      "search_terms": [
        "famous speech audio",
        "spoken word poetry performance"
      ],
      "keywords": ["speech", "vocal"]
    },
    "02_ambient": {
      "label": "Ambient Textures",
      "description": "Background layers and atmospheric beds.",
      "search_terms": [
        "field recording rainforest",
        "urban night ambient"
      ],
      "keywords": ["ambient", "texture"]
    }
  }
}
```

### 4. Download Audio

```powershell
# Interactive search — browse and pick
python -m media_harvest download -p my-song --search

# Batch download top 3 results per search term
python -m media_harvest download -p my-song --batch --max-results 3

# Download a specific URL
python -m media_harvest download -p my-song --url "https://youtube.com/watch?v=..." --category 01_vocals

# Preview without downloading
python -m media_harvest download -p my-song --search --dry-run
```

### 5. Transcribe

```powershell
# Transcribe all downloads with Whisper
python -m media_harvest transcribe -p my-song

# Use a larger model for better accuracy
python -m media_harvest transcribe -p my-song --model medium
```

Each audio file gets a `.txt` transcript with timestamped segments — use these to find the exact clips you want.

### 6. Define Extractions

After reviewing transcripts, edit `projects/my-song/extractions.json` to define which clips to cut:

```json
{
  "01_intro_hooks": [
    {
      "source": "01_vocals/Famous_Speech.wav",
      "clips": [
        {
          "start": 12.5,
          "end": 18.0,
          "name": "key_phrase_hook",
          "note": "The iconic opening line — perfect for song intro"
        }
      ]
    }
  ]
}
```

### 7. Extract Samples

```powershell
python -m media_harvest extract -p my-song
```

Clips land in `projects/my-song/samples/`, organized by category and ready for your DAW.

## CLI Reference

| Command | Description |
|---|---|
| `init <name>` | Create a new project with template configs |
| `download -p <name>` | Download audio (`--search`, `--batch`, or `--url`) |
| `transcribe -p <name>` | Transcribe all downloaded audio with Whisper |
| `extract -p <name>` | Extract clips based on `extractions.json` |
| `status -p <name>` | Show project status & stats |
| `list` | List all projects |

### Download Flags

| Flag | Default | Description |
|---|---|---|
| `--search` | — | Interactive: browse results, pick which to download |
| `--batch` | — | Auto-download top N results per search term |
| `--url <URL>` | — | Download a single URL |
| `--category <id>` | all | Target a specific category |
| `--max-results <N>` | 5 | Max search results per query |
| `--max-duration <s>` | 600 | Skip videos longer than N seconds |
| `--sample-rate <Hz>` | 44100 | WAV sample rate |
| `--bit-depth <16\|24\|32>` | 16 | WAV bit depth |
| `--dry-run` | — | Preview without downloading |

## Project Structure

```
media-harvest/
├── media_harvest/           # Core Python package
│   ├── __main__.py          # CLI entry point
│   ├── config.py            # Auto-detection & project paths
│   ├── download.py          # YouTube search & download
│   ├── transcribe.py        # Whisper + captions + Gemini
│   ├── extract.py           # Sample extraction
│   └── utils.py             # Shared utilities
├── projects/                # Your creative projects
│   ├── _example_song/       # Song production example
│   └── _example_documentary/# Documentary example
├── requirements.txt
├── setup.ps1
├── .env.example
└── .gitignore
```

Each project in `projects/` follows this structure:

```
my-project/
├── presets.json        # Search categories & YouTube queries
├── extractions.json    # Clip extraction map (timestamps)
├── output/             # Downloaded audio files + manifests
│   ├── 01_category/
│   ├── 02_category/
│   ├── manifest.json
│   └── transcripts.json
└── samples/            # Extracted clips, ready for DAW
    ├── 01_intro/
    └── 02_textures/
```

## Prerequisites

- **Python 3.10+**
- **FFmpeg** — auto-detected from PATH, or set `FFMPEG_PATH` in `.env`
- **GPU recommended** for Whisper `medium`/`large` models (CPU works for `tiny`/`base`)

## Origins

This toolkit was born from the [auction-audio-pipeline](https://github.com/eric-rolph/media-harvest/tree/main/projects/_example_song) project — a system for downloading and sampling auction chant audio for electronic music production. The patterns proved useful enough to generalize into a reusable tool for any creative media harvesting workflow.

## License

MIT
