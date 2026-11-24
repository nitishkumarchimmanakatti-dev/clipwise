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


def validate_youtube_url(url: str, ownership_confirmed: bool = False, rights_confirmed: bool = False) -> str:
    """Validate that the input is a single YouTube video URL (disallowing playlists and channels)
    and that the user has verified ownership.
    """
    clean_url = url.strip()
    if not clean_url:
        raise ValueError("Provided URL is empty.")

    if not (ownership_confirmed or rights_confirmed):
        raise ValueError(
            "Copyright confirmation required: You must check 'I own the rights to this video' "
            "to process a YouTube URL."
        )

    parsed = urlparse(clean_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URL structure: {clean_url}")

    hostname = (parsed.hostname or "").lower()
    if not any(domain in hostname for domain in ["youtube.com", "youtu.be"]):
        raise ValueError(f"URL domain is not YouTube: {hostname}")

    # Reject channels and playlists
    if any(p in parsed.path.lower() for p in ["/channel/", "/@", "/c/", "/user/", "/playlist"]):
        raise ValueError("Channel and playlist URLs are strictly disallowed. Please submit a single video.")

    if "list=" in parsed.query:
        raise ValueError("Playlists are not supported. Please provide a direct, single video URL.")

    return extract_video_id(clean_url)


def download_video(
    url: str,
    force: bool = False,
    ownership_confirmed: bool = True,
    rights_confirmed: bool = True,
) -> Tuple[Path, Path, Dict[str, Any]]:
    """Download best mp4 under 1080p and extract audio for transcription.
    
    Returns:
        (video_file_path, audio_file_path, metadata_dict)
    """
    video_id = validate_youtube_url(url, ownership_confirmed=ownership_confirmed, rights_confirmed=rights_confirmed)
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
        "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "outtmpl": video_target_pattern,
        "noplaylist": True,
        "merge_output_format": "mp4",
        "concurrent_fragment_downloads": 5,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "tv", "mweb", "web_creator"],
            }
        },
        "js_runtimes": {"node": {}},
        "remote_components": {"ejs:github"},
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "postprocessors": [
            {
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }
        ],
    }

    # Support cookies from file or environment variable for datacenter bypassing
    import os
    cookies_env = os.getenv("YOUTUBE_COOKIES")
    candidate_cookie_paths = [
        Path("/app/cookies.txt"),
        Path("cookies.txt"),
        DOWNLOADS_DIR / "cookies.txt"
    ]
    cookies_file = next((p for p in candidate_cookie_paths if p.exists()), None)

    if cookies_env:
        target_path = Path("/app/cookies.txt") if Path("/app").exists() else DOWNLOADS_DIR / "cookies.txt"
        try:
            target_path.write_text(cookies_env)
            cookies_file = target_path
        except Exception:
            pass

    if cookies_file and cookies_file.exists():
        ydl_opts["cookiefile"] = str(cookies_file)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract metadata first to check if video is an ongoing live stream
            info_check = ydl.extract_info(url, download=False)
            if not info_check:
                raise RuntimeError(f"Failed to fetch metadata for URL: {url}")
            if info_check.get("is_live") or info_check.get("live_status") == "is_live":
                raise ValueError(
                    "This YouTube video is currently an ACTIVE LIVE STREAM! "
                    "Clipwise generates clips from completed videos or finished live stream recordings. "
                    "Please use a completed video or wait until this stream ends."
                )

            # Allow full duration analysis (up to 2 hours) so clips can reach the final climax
            MAX_SEC = 7200
            if info_check.get("duration") and info_check["duration"] > MAX_SEC:
                from yt_dlp.utils import download_range_func
                ydl.params["download_ranges"] = download_range_func(None, [(0, MAX_SEC)])

            info = ydl.extract_info(url, download=True)
            if not info:
                raise RuntimeError(f"Failed to fetch metadata for URL: {url}")
    except Exception as e:
        err_msg = str(e)
        lower_err = err_msg.lower()
        if (
            "sign in to confirm" in lower_err
            or "not a bot" in lower_err
            or "cookies" in lower_err
            or ("bot" in lower_err and "confirm" in lower_err)
        ):
            raise RuntimeError(
                "YouTube has blocked this cloud server with an anti-bot challenge for this video. "
                "👉 Solution: Please switch to the 'Upload Video' tab to upload your video file directly "
                "(which is 100% reliable and never blocked), or run Clipwise locally on your Mac."
            ) from e
        if "This live event has ended" in err_msg:
            raise RuntimeError(
                "This YouTube Live stream has ended and the recording is not yet available for processing. "
                "Please use a completed YouTube video or upload the video directly via the 'Upload Video' tab."
            ) from e
        raise

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
