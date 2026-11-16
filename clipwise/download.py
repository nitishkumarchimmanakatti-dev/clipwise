"""YouTube video and audio downloader using yt-dlp."""

from pathlib import Path
from typing import Dict, Any, Tuple
import json
import re
from urllib.parse import urlparse, parse_qs
import yt_dlp

from clipwise.config import DOWNLOADS_DIR, OUTPUT_DIR


def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from various URL formats.
    
    Supports:
      - https://www.youtube.com/watch?v=VIDEO_ID
      - https://youtu.be/VIDEO_ID
      - https://www.youtube.com/embed/VIDEO_ID
      - https://www.youtube.com/v/VIDEO_ID
      - https://www.youtube.com/shorts/VIDEO_ID
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string.")

    parsed = urlparse(url.strip())
    hostname = parsed.hostname or ""

    if "youtube.com" in hostname:
        if parsed.path == "/watch":
            qs = parse_qs(parsed.query)
            if "v" in qs and qs["v"]:
                return qs["v"][0]
        elif parsed.path.startswith(("/embed/", "/v/", "/shorts/")):
            parts = parsed.path.strip("/").split("/")
            if len(parts) >= 2:
                return parts[1]
    elif "youtu.be" in hostname:
        clean_path = parsed.path.strip("/")
        if clean_path:
            return clean_path.split("?")[0]

    # Fallback to regex check for an 11-character video ID
    match = re.search(r"[a-zA-Z0-9_-]{11}", url)
    if match:
        return match.group(0)

    raise ValueError(f"Could not extract a valid YouTube video ID from URL: {url}")


def validate_youtube_url(url: str) -> str:
    """Validate that the input is a single YouTube video URL (disallowing playlists)."""
    clean_url = url.strip()
    if not clean_url:
        raise ValueError("Provided URL is empty.")

    parsed = urlparse(clean_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URL structure: {clean_url}")

    hostname = (parsed.hostname or "").lower()
    if not any(domain in hostname for domain in ["youtube.com", "youtu.be"]):
        raise ValueError(f"URL domain is not YouTube: {hostname}")

    # Check for playlist-only URLs
    if "list=" in parsed.query and "v=" not in parsed.query and not parsed.path.startswith("/watch"):
        raise ValueError("Playlist URLs are not supported. Please provide a single video URL.")

    return extract_video_id(clean_url)


def download_video(url: str, force: bool = False) -> Tuple[Path, Path, Dict[str, Any]]:
    """Download best mp4 under 1080p and extract audio for transcription.
    
    Returns:
        (video_file_path, audio_file_path, metadata_dict)
    """
    video_id = validate_youtube_url(url)
    dest_dir = DOWNLOADS_DIR / video_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    meta_file = dest_dir / "metadata.json"
    video_target_pattern = str(dest_dir / "source.%(ext)s")
    audio_file = dest_dir / "audio.wav"
    video_file = dest_dir / "source.mp4"

    # Reuse existing downloads if already present and not forced
    if not force and video_file.exists() and audio_file.exists() and meta_file.exists():
        with open(meta_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        return video_file, audio_file, metadata

    ydl_opts = {
        "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
        "outtmpl": video_target_pattern,
        "noplaylist": True,
        "merge_output_format": "mp4",
        "quiet": False,
        "no_warnings": False,
        "postprocessors": [
            {
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }
        ],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if not info:
            raise RuntimeError(f"Failed to fetch metadata for URL: {url}")

    # Save clean metadata
    metadata = {
        "id": video_id,
        "title": info.get("title", ""),
        "duration": info.get("duration", 0),
        "channel": info.get("channel", info.get("uploader", "")),
        "channel_id": info.get("channel_id", ""),
        "description": info.get("description", ""),
        "view_count": info.get("view_count", 0),
        "webpage_url": info.get("webpage_url", url),
        "thumbnail": info.get("thumbnail", ""),
    }

    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    # Also extract 16kHz mono WAV for whisper transcription
    import subprocess
    cmd = [
        "ffmpeg", "-y", "-i", str(video_file),
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(audio_file)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return video_file, audio_file, metadata
