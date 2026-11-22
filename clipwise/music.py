"""Music management, license logging, mood matching, and sidechain ducking mix engine."""

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import os
import csv
import json
import logging
from datetime import datetime

from clipwise.config import CLIPWISE_MUSIC_DIR, MUSIC_LICENSES_FILE

logger = logging.getLogger("clipwise.music")

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}

# Keyword indicators for mood detection (English + Hindi/Hinglish)
MOOD_KEYWORDS = {
    "emotional": [
        "miss", "yaad", "dard", "life", "mother", "father", "maa", "struggle",
        "tears", "rona", "pain", "alone", "sad", "breakup", "heart", "broken",
        "hard times", "lost", "regret", "emotional", "qismat", "dukh"
    ],
    "motivational": [
        "never give up", "jeetenge", "himmat", "fail", "failure", "winner",
        "success", "discipline", "focus", "dream", "hustle", "work hard",
        "power", "grind", "possible", "strength", "believe", "champions", "lead",
        "attitude", "podcast", "mindset", "money", "wealth", "billionaire", "rich",
        "future", "elon", "ai", "tech", "build", "rules", "goal", "drive", "energy",
        "strategy", "win", "alpha", "sigma", "mentality", "warrior", "advice",
        "motivation", "motivational", "inspire", "hard work", "consistency", "leader"
    ],
    "romantic": [
        "love", "pyaar", "dil", "ishq", "mohabbat", "relationship", "partner",
        "husband", "wife", "crush", "romantic", "care", "together", "soulmate"
    ],
    "comedy": [
        "joke", "funny", "laugh", "haso", "prank", "crazy", "comedy", "lmao",
        "pagal", "hansi", "meme", "hilarious", "ridiculous"
    ]
}


def init_music_licenses(licenses_file: Path = MUSIC_LICENSES_FILE) -> None:
    """Ensure music_licenses.csv exists with proper schema."""
    if not licenses_file.exists():
        licenses_file.parent.mkdir(parents=True, exist_ok=True)
        with open(licenses_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["filename", "license_note", "source", "added_at"])


def log_music_license(
    filename: str,
    license_note: str = "YouTube Audio Library (Royalty-free)",
    source: str = "YouTube Audio Library",
    licenses_file: Path = MUSIC_LICENSES_FILE,
) -> None:
    """Record a track's filename and license note in music_licenses.csv."""
    init_music_licenses(licenses_file)
    existing_records = set()
    try:
        with open(licenses_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if row:
                    existing_records.add(row[0])
    except Exception:
        pass

    if filename not in existing_records:
        with open(licenses_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([filename, license_note, source, datetime.now().isoformat()])


def get_licensed_tracks(
    music_dir: Path = CLIPWISE_MUSIC_DIR,
    licenses_file: Path = MUSIC_LICENSES_FILE,
) -> List[Dict[str, Any]]:
    """Scan music directory for licensed audio tracks and cross-reference with licenses CSV."""
    init_music_licenses(licenses_file)
    if not music_dir.exists():
        return []

    license_map: Dict[str, Dict[str, str]] = {}
    try:
        with open(licenses_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                license_map[row.get("filename", "")] = {
                    "license_note": row.get("license_note", "YouTube Audio Library (Royalty-free)"),
                    "source": row.get("source", "YouTube Audio Library"),
                }
    except Exception:
        pass

    tracks: List[Dict[str, Any]] = []
    for file in sorted(music_dir.iterdir()):
        if file.is_file() and file.suffix.lower() in AUDIO_EXTENSIONS and not file.name.startswith("."):
            info = license_map.get(file.name, {
                "license_note": "YouTube Audio Library (Royalty-free)",
                "source": "YouTube Audio Library"
            })
            if file.name not in license_map:
                log_music_license(file.name, info["license_note"], info["source"], licenses_file)

            name = file.stem.replace("_", " ").title()
            name_lower = file.stem.lower()
            if "solitude" in name_lower or "sad" in name_lower or "quiet" in name_lower or "emotional" in name_lower:
                mood = "emotional"
            elif "rise" in name_lower or "above" in name_lower or "motivat" in name_lower or "power" in name_lower:
                mood = "motivational"
            elif "sunset" in name_lower or "romance" in name_lower or "love" in name_lower or "melod" in name_lower:
                mood = "romantic"
            elif "mischief" in name_lower or "sneaky" in name_lower or "comedy" in name_lower or "funny" in name_lower:
                mood = "comedy"
            else:
                mood = "general"

            tracks.append({
                "id": file.stem,
                "name": name,
                "filename": file.name,
                "file_path": str(file.resolve()),
                "file_exists": True,
                "mood": mood,
                "license": info["license_note"],
                "source": info["source"],
            })

    return tracks


def ensure_music_available(
    music_dir: Path = CLIPWISE_MUSIC_DIR,
    raise_if_empty: bool = False,
) -> List[Dict[str, Any]]:
    """Check if music directory has valid tracks.
    
    If empty:
        - If raise_if_empty: raises RuntimeError refusing to run.
        - Otherwise: logs a warning and returns an empty list.
    """
    tracks = get_licensed_tracks(music_dir)
    if not tracks:
        msg = f"Music directory '{music_dir}' is empty. No licensed tracks found."
        logger.warning(msg)
        if raise_if_empty:
            raise RuntimeError(f"Refusing to run music step: {msg} Please place licensed tracks from YouTube Audio Library into {music_dir}.")
        return []
    return tracks


def list_available_tracks(music_dir: Path = CLIPWISE_MUSIC_DIR) -> List[Dict[str, Any]]:
    """Return all available tracks with paths for UI selection."""
    tracks = get_licensed_tracks(music_dir)
    if tracks:
        return tracks

    # Fallback to bundled tracks in music_assets if user folder is empty
    bundled_dir = Path(__file__).parent / "music_assets" / "tracks"
    if bundled_dir.exists():
        manifest_path = Path(__file__).parent / "music_assets" / "music_library.json"
        manifest = {}
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            except Exception:
                pass
        meta_by_file = {t["filename"]: t for t in manifest.get("tracks", [])}

        bundled_tracks = []
        for f in sorted(bundled_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS:
                meta = meta_by_file.get(f.name, {})
                bundled_tracks.append({
                    "id": meta.get("id", f.stem),
                    "name": meta.get("name", f.stem.replace("_", " ").title()),
                    "filename": f.name,
                    "file_path": str(f.resolve()),
                    "file_exists": True,
                    "mood": meta.get("mood", "general"),
                    "license": meta.get("license", "Royalty-free"),
                    "source": "Clipwise Bundled Library",
                })
        return bundled_tracks
    return []


def get_track_by_id(track_id: str, music_dir: Path = CLIPWISE_MUSIC_DIR) -> Optional[Dict[str, Any]]:
    """Retrieve specific track by its ID."""
    for t in list_available_tracks(music_dir):
        if t.get("id") == track_id and t.get("file_exists"):
            return t
    return None


def get_track_for_mood(mood: Optional[str], music_dir: Path = CLIPWISE_MUSIC_DIR) -> Optional[Dict[str, Any]]:
    """Return track dictionary matching mood, or None if mood is None."""
    if not mood:
        return None
    for t in list_available_tracks(music_dir):
        if t.get("mood", "").lower() == mood.lower() and t.get("file_exists"):
            t_copy = dict(t)
            t_copy["mood"] = mood.lower()
            return t_copy
    tracks = list_available_tracks(music_dir)
    if tracks:
        t_copy = dict(tracks[0])
        t_copy["mood"] = mood.lower()
        return t_copy
    return None


def detect_clip_mood(candidate_or_text: Any) -> Tuple[Optional[str], str]:
    """Analyze transcript, word pacing, and pauses to determine if background music is called for.
    
    Accepts either a candidate dict or a string.
    Returns:
        (mood_string_or_None, reason_string)
    """
    if isinstance(candidate_or_text, dict):
        text = candidate_or_text.get("text", "").lower()
        words = candidate_or_text.get("words", [])
        duration = candidate_or_text.get("duration", 1.0)
    else:
        text = str(candidate_or_text).lower()
        words = []
        duration = 1.0

    matched_moods: Dict[str, List[str]] = {}
    for mood, kws in MOOD_KEYWORDS.items():
        hits = [kw for kw in kws if kw in text]
        if hits:
            matched_moods[mood] = hits

    word_count = len(words) if words else len(text.split())
    wpm = (word_count / duration) * 60.0 if duration > 0 else 120.0

    if "emotional" in matched_moods:
        hits_str = ", ".join(matched_moods["emotional"][:2])
        if wpm < 130:
            return "emotional", f"Emotional: reflective speech pace ({int(wpm)} wpm) + keyword '{hits_str}'"
        return "emotional", f"Emotional: keyword '{hits_str}'"

    if "motivational" in matched_moods:
        hits_str = ", ".join(matched_moods["motivational"][:2])
        return "motivational", f"Motivational: high-energy comeback theme + keyword '{hits_str}'"

    if "romantic" in matched_moods:
        hits_str = ", ".join(matched_moods["romantic"][:2])
        return "romantic", f"Romantic: keyword '{hits_str}'"

    if "comedy" in matched_moods:
        hits_str = ", ".join(matched_moods["comedy"][:2])
        return "comedy", f"Comedy: lighthearted timing + keyword '{hits_str}'"

    return None, "No background music needed: informational speech with no strong emotional cue"


def select_track_for_clip(
    candidate: Dict[str, Any],
    music_dir: Path = CLIPWISE_MUSIC_DIR,
    force_music: bool = False,
) -> Optional[Dict[str, Any]]:
    """Select background music track for clip from licensed folder with graceful empty-folder warning."""
    tracks = get_licensed_tracks(music_dir)
    if not tracks:
        logger.warning(f"No licensed tracks found in {music_dir}. Skipping background music.")
        return None

    mood, reason = detect_clip_mood(candidate)
    if not mood and not force_music:
        return None

    target_mood = mood or "general"
    chosen_track = None
    for t in tracks:
        if target_mood.lower() in t["name"].lower():
            chosen_track = dict(t)
            break

    if not chosen_track:
        chosen_track = dict(tracks[0])

    chosen_track["mood"] = target_mood
    chosen_track["reason"] = reason if mood else "Selected from licensed library"
    return chosen_track


def get_ducking_audio_filter(
    clip_dur: float,
    speech_volume: float = 1.0,
    music_volume: float = 0.10,  # -20 dB under speech
    fade_duration: float = 0.5,
) -> str:
    """Generate FFmpeg sidechain ducking audio filter string.
    
    Music is added at -20 dB (0.10 volume) under speech with dynamic ducking,
    fading in over 0.5s and fading out over 0.5s.
    """
    fade_out_start = max(0.1, round(clip_dur - fade_duration, 2))
    return (
        f"[0:a]volume={speech_volume}[speech];"
        f"[1:a]afade=t=in:ss=0:d={fade_duration},"
        f"afade=t=out:st={fade_out_start}:d={fade_duration},"
        f"volume={music_volume}[music];"
        f"[music][speech]sidechaincompress=threshold=0.08:ratio=6:attack=50:release=350[ducked_music];"
        f"[speech][ducked_music]amix=inputs=2:duration=first[aout]"
    )
