# 🎙️ Aural Archive

**A general-purpose audio transcription and sonic archival toolkit.**

Aural Archive is a suite of tools designed to facilitate the collection, transcription, and time-coding of "found sound" and field recordings. Whether analyzing historical archives, documenting environmental soundscapes, or conducting qualitative media research, this toolkit provides a structured pipeline for organizing audio data and extracting meaningful segments with precision.

## Core Purpose

This tool is intended for researchers, archivists, sound artists, and ethnomusicologists to:
1. **Catalog** audio from diverse sources into structured research projects.
2. **Transcribe** spoken word or sonic events with high-fidelity time-codes.
3. **Analyze** long-form recordings to identify and preserve specific "found sound" moments.
4. **Export** precise clips for further study or creative use in digital audio workstations (DAWs).

## Key Features

- **🔍 Research-First Acquisition** — Gather audio from digital repositories or local field recordings.
- **🎙️ Time-Coded Transcription**:
  - **OpenAI Whisper** — Local, high-accuracy speech-to-text with segment-level timestamps.
  - **Annotation Engine** — Support for metadata-rich transcripts for deep analysis.
- **✂️ Selective Archiving** — Extract precise clips by timestamp to curate specific sonic events.
- **📁 Structured Data Organization** — Every project maintains a clear manifest, sidecar metadata, and a verified audit trail of all operations.

## Quick Start

### 1. Setup

```powershell
git clone https://github.com/eric-rolph/aural-archive.git
cd aural-archive
.\setup.ps1
.\venv\Scripts\Activate.ps1
```

### 2. Initialize a Study Project

```powershell
python -m media_harvest init field-observation-01
```

This creates a structured directory at `projects/field-observation-01/` with study-specific configuration templates.

### 3. Define Acquisition Presets

Edit `projects/field-observation-01/presets.json` to define your observation categories and capture parameters:

```json
{
  "categories": {
    "01_field_recordings": {
      "label": "Field Recordings",
      "description": "Environmental audio captured during site visits.",
      "search_terms": ["site A ambient", "industrial drone"],
      "keywords": ["ambient", "drone", "site-a"]
    },
    "02_archival_footage": {
      "label": "Archival Sources",
      "description": "Historical records and digital archives.",
      "search_terms": ["1950s urban history", "oral history interview"],
      "keywords": ["history", "archive", "speech"]
    }
  }
}
```

### 4. Acquire Audio

```powershell
# Interactive acquisition — browse and select for archival
python -m media_harvest download -p field-observation-01 --search

# Direct archival from a specific URL or repository link
python -m media_harvest download -p field-observation-01 --url "https://..." --category 02_archival_footage
```

### 5. Generate Transcripts

```powershell
# Transcribe all archived files to create time-coded research logs
python -m media_harvest transcribe -p field-observation-01 --model medium
```

Each audio file generates a `.txt` transcription with sub-second timestamps, allowing you to pinpoint specific sonic events for your analysis.

### 6. Mark Observations for Extraction

Review your transcripts and define precise clips in `projects/field-observation-01/extractions.json`:

```json
{
  "archival_highlights": [
    {
      "source": "02_archival_footage/Historical_Interview.wav",
      "clips": [
        {
          "start": 45.2,
          "end": 52.8,
          "name": "significant_quote",
          "note": "A primary observation regarding urban development."
        }
      ]
    }
  ]
}
```

### 7. Extract Samples

```powershell
python -m media_harvest extract -p field-observation-01
```

Clips are saved in `projects/field-observation-01/samples/`, organized by observation category.

## CLI Reference

| Command | Description |
|---|---|
| `init <name>` | Initialize a new archival project |
| `download -p <name>` | Acquire audio (`--search`, `--batch`, or `--url`) |
| `transcribe -p <name>` | Generate time-coded transcripts for all project audio |
| `extract -p <name>` | Cut precise clips based on `extractions.json` |
| `status -p <name>` | View project statistics and archival progress |
| `list` | List all active projects |

## Project Structure

```
aural-archive/
├── media_harvest/           # Analysis core
├── projects/                # Archival projects
│   ├── _example_field_study/          # Environmental study example
│   └── _example_sonic_exploration/    # Creative archaeology example
├── requirements.txt
├── setup.ps1
└── .env.example
```

## Legal & Ethical Use

Aural Archive is designed for researchers, archivists, and creators to manage and analyze recordings in accordance with applicable laws. 

**Important Notice:**
- This tool is intended only for use with audio for which you have the legal right to access, download, or analyze (e.g., public domain content, content with appropriate Creative Commons licenses, or recordings you own).
- Users are responsible for complying with the terms of service of any digital repositories or platforms accessed via this tool.
- Unauthorized transcription or distribution of copyrighted material may be against the law in your jurisdiction.
- The developers of Aural Archive do not condone or support the use of this tool for copyright infringement.

## License

MIT
