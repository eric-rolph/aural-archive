# 🎙️ Aural Archive

**A general-purpose audio transcription and sonic archival toolkit.**

Aural Archive is a suite of tools designed to facilitate the collection, transcription, and time-coding of "found sound," field recordings, and digital artifacts. Built for researchers, ethnomusicologists, and sound artists, it provides a structured pipeline for organizing audio data and extracting meaningful segments with archival precision.

## 🏺 Core Purpose

This toolkit is designed to:
1. **Archive** audio from diverse digital repositories and local field recordings into structured research projects.
2. **Transcribe** spoken word and sonic events with high-fidelity time-codes using local AI models.
3. **Analyze** long-form recordings to identify and preserve specific "found sound" moments.
4. **Preserve Context** via advanced JSON sidecar metadata and an SQLite-based state journal.

## ✨ Key Features

- **🔍 Research-First Acquisition** — The `capture` command allows for targeted, ethical gathering of audio artifact metadata and binary data.
- **🔌 Plugin Architecture** — Modular `Extractor` system for easily adding new acquisition sources (YouTube, local, HTML, etc.).
- **📜 SQLite State Journal** — Robust state management ensures idempotency, crash recovery, and a clear audit trail of all archival jobs.
- **🎙️ Time-Coded Transcription**:
  - **OpenAI Whisper** — Local, high-accuracy speech-to-text with segment-level timestamps.
  - **Multi-Strategy** — Support for YouTube captions, Whisper, and Gemini Vision transcripts.
- **📁 Advanced Organization** — Automatic generation of `.info.json` sidecar metadata and generic, research-oriented project structures.

## 🚀 Quick Start

### 1. Setup
```powershell
git clone https://github.com/eric-rolph/aural-archive.git
cd aural-archive
.\setup.ps1
.\venv\Scripts\Activate.ps1
```

### 2. Initialize a Research Project
```powershell
python -m media_harvest init archival-study-001
```

### 3. Capture Audio Artifacts
```powershell
# Interactive search & select
python -m media_harvest capture -p archival-study-001 --mode search
```

### 4. Transcribe Findings
```powershell
python -m media_harvest transcribe -p archival-study-001
```

### 5. Review & Analyze
```powershell
# Read transcript + metadata directly in terminal
python -m media_harvest view -p archival-study-001 --num 1 --meta

# Check archival metrics & level
python -m media_harvest stats -p archival-study-001
```

## 🛠️ CLI Reference

| Command | Description |
|---|---|
| `init <name>` | Initialize a new archival project with templates |
| `capture -p <name>`| Acquire audio artifacts (`--mode search`, `batch`, or `url`) |
| `journal -p <name>`| Inspect and manage the archival queue and job states |
| `transcribe -p <name>`| Generate time-coded transcripts for all project audio |
| `view -p <name>` | View transcripts and metadata sidecars in the terminal |
| `stats -p <name>` | View deep archival metrics and storage statistics |
| `extract -p <name>`| Cut precise clips based on `extractions.json` |
| `doctor` | Check health of dependencies (FFmpeg, yt-dlp, etc.) |
| `list` | List all active archival projects |

## 📁 Project Structure
```
aural-archive/
├── media_harvest/           # Core library & plugins
├── projects/                # Archival research projects
│   ├── archival-study-01/   # User-defined study
│   │   ├── presets.json     # Capture parameters
│   │   ├── extractions.json # Sample definitions
│   │   ├── output/          # Archived recordings & metadata
│   │   └── samples/         # Extracted sonic events
├── LICENSE.md               # MIT + Ethical Archival Notice
├── setup.ps1
└── README.md
```

## ⚖️ Legal & Ethical Use
Aural Archive is designed for researchers and archivists to manage recordings in accordance with applicable laws. 
- **Personal/Research Use Only**: Intended for public domain content or content you have a legal right to access.
- **Respect TOSe**: Users are responsible for complying with the Terms of Service of all repositories accessed.
- **No Infringement**: We do not condone or support the use of this tool for copyright infringement.

## 📜 License
Distributed under the MIT License with an included **Ethical Archival Research Notice**. See [LICENSE.md](./LICENSE.md) for details.
