# Clipwise v2 ✂️

> **Production AI Shorts Studio: Turn long videos into high-retention 9:16 vertical clips with strong hooks, captions in the bottom blur zone, and situational background music.**

Clipwise v2 is a self-hosted, public web application and API that transforms uploaded videos or authorized YouTube links into viral YouTube Shorts, TikToks, and Instagram Reels.

---

## ⚡ Key Capabilities in v2

- **Hook-First Clip Selection**: Every clip starts strictly on a hook (curiosity questions, bold claims, numbers), rejects filler openers (`"so basically"`, `"um"`), resolves on a complete thought, and holds $0.3\text{s}–0.5\text{s}$ clean silence at the end. Target length: 25–45s (clamped to 15–60s).
- **Bottom Blur-Zone Captions**: Captions are rendered strictly in the bottom blurred canvas ($Y \approx 1400–1700$), keeping the main 16:9 video 100% visible and unobstructed.
- **Multilingual Typography (Noto Sans Devanagari)**: Bundles Noto Sans and Noto Sans Devanagari fonts so English, Hindi, and Hinglish subtitles render crisp glyphs with zero missing box characters.
- **Situational Music Ducking**: Adds licensed background music *only* when the moment calls for it (Emotional, Motivational, Romantic, Comedy). Music automatically ducks down to 12–18% under speech using FFmpeg sidechain compression and fades in/out smoothly.
- **Single-User Admin Authentication**: Protects the public web app behind a master password (`CLIPWISE_PASSWORD`) via HTTP-only session cookies to guard compute resources.
- **Strict Copyright Rules**: Primary input is direct video upload (MP4/MOV). YouTube URLs require checking `"I own the rights to this video"` before processing; every confirmation is logged. Single videos only (playlists and channel URLs are blocked).
- **Persistent Storage & Auto-Cleanup**: Rendered clips are saved with version IDs (`_v1`, `_v2`), eliminating stale cache playback. Raw originals auto-expire after 7 days (`ORIGINALS_TTL_DAYS=7`). Safe deletion requires typing `"DELETE"`.
- **Full Review & Export Studio**: Vertical 9:16 video player, editable metadata (title, description, tags), music track switcher, re-trim start/end handles, and 1-click **Download Approved (.ZIP)** export.

---

## 🌐 Public Deployment Guide

Clipwise v2 can be deployed anywhere with Docker and runs in any modern browser (Chrome, Safari, Firefox, iOS, Android) with zero client install.

### Option A: Railway (Recommended)

1. Push this repository to your GitHub account.
2. In [Railway](https://railway.app), click **New Project** → **Deploy from GitHub repo**.
3. Railway automatically detects the production `Dockerfile`.
4. Go to **Settings** → **Volumes** → **Add Volume**:
   - Mount Path: `/data`
5. Go to **Variables** and set:
   ```env
   CLIPWISE_PASSWORD=your_strong_admin_password
   CLIPWISE_DATA_DIR=/data
   ORIGINALS_TTL_DAYS=7
   MAX_UPLOAD_SIZE_MB=500
   DEFAULT_CAPTION_COLOR=#FFD700
   ```
6. Click **Deploy**. Railway will provide a public HTTPS URL (e.g., `https://your-app.up.railway.app`).

---

### Option B: Linux VPS (Hetzner, DigitalOcean, Linode)

For multi-core CPU performance and unrestricted speed:

1. SSH into your VPS with Docker and Docker Compose installed:
   ```bash
   git clone https://github.com/your-username/clipwise.git
   cd clipwise
   ```
2. Create an `.env` file:
   ```bash
   CLIPWISE_PASSWORD=your_strong_admin_password
   CLIPWISE_DATA_DIR=/data
   MAX_UPLOAD_SIZE_MB=500
   ORIGINALS_TTL_DAYS=7
   DEFAULT_CAPTION_COLOR=#FFD700
   ```
3. Start the service:
   ```bash
   docker compose up -d
   ```
4. Access Clipwise at `http://YOUR_SERVER_IP:8000`. (Set up a reverse proxy like Caddy or Nginx with Let's Encrypt for custom domains and automatic SSL).

---

### Option C: Render

1. Create a **New Web Service** from your GitHub repo.
2. Environment: **Docker**.
3. Under **Disks**, attach a persistent disk mounted at `/data`.
4. Set environment variables (`CLIPWISE_PASSWORD`, `CLIPWISE_DATA_DIR=/data`, etc.).

---

## ⚙️ Environment Variables

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `CLIPWISE_PASSWORD` | *(empty)* | Master password required to access and process videos. If unset, runs in open local dev mode. |
| `CLIPWISE_DATA_DIR` | `~/Clipwise` or `/data` | Path where outputs, originals, and logs are stored. |
| `MAX_UPLOAD_SIZE_MB` | `500` | Maximum allowed video file size for uploads (in MB). |
| `ORIGINALS_TTL_DAYS` | `7` | Number of days before downloaded/uploaded raw videos auto-expire (rendered shorts are never expired). |
| `DEFAULT_CAPTION_COLOR`| `#FFD700` | Default color for burned-in subtitles (Warm Gold `#FFD700`, Electric Yellow `#1BF7FF`, White `#FFFFFF`). |
| `CLIPWISE_WHISPER_MODEL`| `base` | Faster-Whisper model size (`tiny`, `base`, `small`). |
| `GEMINI_API_KEY` | *(empty)* | Optional API key for LLM hook scoring enrichment. |
| `OPENAI_API_KEY` | *(empty)* | Optional alternative OpenAI key for LLM scoring. |

---

## 🎵 How to Add Licensed Music Tracks

Background music is driven by the manifest at `clipwise/music/music_library.json`.

1. Place your royalty-free MP3 file inside `clipwise/music/tracks/` (e.g. `my_track.mp3`).
2. Add an entry to `clipwise/music/music_library.json`:
   ```json
   {
     "id": "motivational_02",
     "name": "Champion Drive",
     "filename": "my_track.mp3",
     "mood": "motivational",
     "tempo": "driving",
     "duration_sec": 85.0,
     "license": "YouTube Audio Library (Royalty Free)",
     "source_url": "https://studio.youtube.com/channel/music",
     "keywords": ["win", "success", "power", "energy"]
   }
   ```
3. The track will immediately be recognized by the mood detector and available in the Web UI review track picker.

---

## 💻 Local Mac Development

```bash
# Activate virtual environment
source .venv/bin/activate

# Run test suite
pytest

# Start local server
python main.py ui --host 127.0.0.1 --port 8000
```
Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.
