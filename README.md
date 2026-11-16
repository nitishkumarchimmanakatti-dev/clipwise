# Clipwise ✂️

> **Turn long YouTube videos into viral 9:16 Shorts with high-retention hooks and burned-in captions.**

Clipwise is a local, privacy-respecting AI shorts generation engine and web application (inspired by Opus Clip and Klap). It downloads a single YouTube video, transcribes it locally using `faster-whisper`, isolates viral hook segments (15–60s) on sentence boundaries, renders 9:16 vertical video with dynamic captions, and generates optimized titles, descriptions, and hashtags for review.

---

## ⚡ Key Capabilities

- **OpusClip-Style Web UI**: Modern dark-mode interface with live progress tracking, vertical video preview player cards, hashtag copying, and approval toggles.
- **Local Speech-to-Text**: Powered by `faster-whisper` (CTranslate2) running locally with Apple Silicon NEON vectorization (`int8` compute) — zero cloud API cost.
- **Smart Sentence Boundary Chunking**: Splits candidates strictly on grammatical sentences and natural speech pauses between 15 and 60 seconds.
- **Viral Hook Scorer**: Detects curiosity questions, emotional exclamations, numeric statistics, pace shifts, and power keywords. Includes an optional pluggable LLM hook scoring layer.
- **Vertical 9:16 FFmpeg Engine**: Automatic conversion to 1080x1920 with blurred background padding or center crop, high-contrast burned-in subtitles, and synced audio.
- **Review & Approval Workflow**: Interactive approval in the Web App or via terminal `review.csv` (`pending`, `approved`, `rejected`).
- **Safety by Design**: Never uploads or publishes automatically. Keeps original downloads separate. Runs strictly local.

---

## 🛠️ Prerequisites

- **macOS** on Apple Silicon (M-series, M1 through M5)
- **Python 3.11+**
- **FFmpeg with libass**:
  ```bash
  brew install ffmpeg-full
  ```

---

## 🚀 Quickstart

### 1. Set Up Virtual Environment

```bash
# Clone or navigate to the repository
cd Clipwise

# Create virtual environment and activate
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

### 2. Launch the Web Application

To use the OpusClip-style browser interface:

```bash
python main.py ui
```

Then open **[http://localhost:8000](http://localhost:8000)** in your browser:
1. Paste any YouTube video link.
2. Choose your preferred clip count (3, 5, or 10) and format (Blurred Background or Center Crop).
3. Click **Generate Clips** and watch the real-time pipeline visualizer.
4. Preview the generated 9:16 vertical shorts, inspect titles and hashtags, approve/reject clips, or download the `.mp4` and `.srt` files directly!

---

### 3. Or Use the Terminal CLI

You can also run the entire pipeline directly from the command line:

```bash
# Process a video into up to 5 shorts
python main.py run "https://www.youtube.com/watch?v=VIDEO_ID" --max-clips 5

# Inspect pending clips awaiting your review
python main.py review

# Approve a clip
python main.py approve <clip_id>

# Reject a clip
python main.py reject <clip_id>
```

#### CLI Options
- `--max-clips <int>`: Maximum number of candidate clips (default: 10).
- `--mode blur|crop`: Reformatting mode (`blur` for blurred background, `crop` for center crop).
- `--force`: Overwrite existing outputs in the video folder.
- `--llm`: Enable optional LLM hook scoring (reads `GEMINI_API_KEY` or `OPENAI_API_KEY`).

---

## 📂 Output Folder Structure

All candidate outputs are stored locally under `~/Clipwise/output/<video_id>/`:

```text
~/Clipwise/
├── downloads/
│   └── <video_id>/
│       ├── source.mp4         # Original downloaded video
│       ├── audio.wav          # Extracted 16kHz audio for Whisper
│       └── metadata.json      # Channel & source metadata
├── output/
│   └── <video_id>/
│       ├── transcript.json    # Complete Whisper transcript with word timestamps
│       ├── review.csv         # Approval tracking sheet
│       ├── <clip_id>.mp4      # Rendered 1080x1920 vertical short
│       ├── <clip_id>.srt      # Word-aligned subtitle file
│       └── <clip_id>_metadata.json # Title, description, hashtags, timestamps
└── clipwise_log.csv           # Persistent log of all pipeline runs
```

---

## 🧪 Running Tests

Clipwise includes unit and end-to-end integration tests:

```bash
source .venv/bin/activate
pytest -v
```

---

## 🔒 Safety & Rights Policy

1. **Explicit URLs Only**: Only processes URLs you directly supply; channel bulk-downloads are forbidden.
2. **Local Storage Only**: No automated uploading, scheduling, or publishing.
3. **Non-Destructive**: Original downloads are retained in `~/Clipwise/downloads/` and will not be deleted automatically.
4. **Audit Log**: Every pipeline run is recorded in `~/Clipwise/clipwise_log.csv`.
