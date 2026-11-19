"""Clipwise Configuration and Path Management."""

from pathlib import Path
import os
import shutil
import subprocess

# Root directories for output and downloads
CLIPWISE_DATA_DIR = Path(os.getenv("CLIPWISE_DATA_DIR", str(Path.home() / "Clipwise")))
OUTPUT_DIR = CLIPWISE_DATA_DIR / "output"
ORIGINALS_DIR = CLIPWISE_DATA_DIR / "originals"
DOWNLOADS_DIR = ORIGINALS_DIR  # Alias for backward-compatibility
LOG_FILE = CLIPWISE_DATA_DIR / "clipwise_log.csv"
CLIPWISE_MUSIC_DIR = Path(os.getenv("CLIPWISE_MUSIC_DIR", str(Path.home() / "Clipwise" / "music")))
MUSIC_LICENSES_FILE = CLIPWISE_MUSIC_DIR / "music_licenses.csv"

# Storage, Upload & Security Constraints
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "2000"))  # 2GB generous limit
ORIGINALS_TTL_DAYS = int(os.getenv("ORIGINALS_TTL_DAYS", "14"))  # 14 days retention
CLIPWISE_PASSWORD = os.getenv("CLIPWISE_PASSWORD", "")  # Empty means open/dev mode
SESSION_SECRET = os.getenv("SESSION_SECRET", "clipwise-v2-super-secret-key-39824")
ENABLE_YOUTUBE_URL = os.getenv("ENABLE_YOUTUBE_URL", "false").lower() in ("true", "1", "yes")

# Caption Styling
DEFAULT_CAPTION_COLOR = os.getenv("DEFAULT_CAPTION_COLOR", "#FFD700")  # Default warm gold
CAPTION_ZONE_MIN_Y = 1400
CAPTION_ZONE_MAX_Y = 1700
CAPTION_BOTTOM_CLEARANCE = 150

# Ensure essential base folders exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)
CLIPWISE_MUSIC_DIR.mkdir(parents=True, exist_ok=True)

# Clip constraints
MIN_CLIP_DURATION = 15.0  # seconds
MAX_CLIP_DURATION = 60.0  # seconds
TARGET_CLIP_DURATION = 35.0  # optimal target for short-form
DEFAULT_MAX_CLIPS = 10

# Whisper Configuration (Optimized for cloud memory efficiency)
WHISPER_MODEL = os.getenv("CLIPWISE_WHISPER_MODEL", "base")
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"

# Video Processing (Vertical 9:16)
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
DEFAULT_RENDER_MODE = "blur"  # 'blur' (blurred background padding) or 'crop' (center crop)

# LLM Hook Scoring (Optional fallback / enrichment)
LLM_PROVIDER = os.getenv("CLIPWISE_LLM_PROVIDER", "gemini")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


def get_ffmpeg_path() -> str:
    """Return path to ffmpeg binary, checking keg-only ffmpeg-full first."""
    candidates = [
        "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg",
        shutil.which("ffmpeg"),
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
    ]
    for c in candidates:
        if c and Path(c).is_file() and os.access(c, os.X_OK):
            return str(c)
    return "ffmpeg"


def has_subtitles_filter() -> bool:
    """Check if ffmpeg build has the 'subtitles' filter enabled (requires libass)."""
    ffmpeg_bin = get_ffmpeg_path()
    try:
        res = subprocess.run([ffmpeg_bin, "-filters"], capture_output=True, text=True)
        return "subtitles" in res.stdout
    except Exception:
        return False


def check_ffmpeg() -> bool:
    """Check whether ffmpeg is available."""
    ffmpeg_bin = get_ffmpeg_path()
    return shutil.which(ffmpeg_bin) is not None or Path(ffmpeg_bin).exists()


def ensure_ffmpeg() -> str:
    """Validate ffmpeg presence or raise a user-friendly error with fix instructions."""
    ffmpeg_bin = get_ffmpeg_path()
    if not (shutil.which(ffmpeg_bin) or Path(ffmpeg_bin).exists()):
        raise RuntimeError(
            "ffmpeg is not installed or not in PATH.\n"
            "Please install it using Homebrew:\n"
            "    brew install ffmpeg\n"
            "and make sure /opt/homebrew/bin is in your PATH."
        )
    return ffmpeg_bin
