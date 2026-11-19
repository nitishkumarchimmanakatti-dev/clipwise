"""Situational background music engine for Clipwise v2."""

import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

MUSIC_DIR = Path(__file__).parent
MANIFEST_PATH = MUSIC_DIR / "music_library.json"
TRACKS_DIR = MUSIC_DIR / "tracks"

# Keyword indicators for mood detection (English + Hindi/Hinglish)
MOOD_KEYWORDS = {
    "emotional": [
        "miss", "yaad", "dard", "life", "mother", "maa", "struggle",
        "emotional", "alone", "cry", "sad", "dukhi", "aansu", "broken", "death"
    ],
    "motivational": [
        "never give up", "jeetenge", "himmat", "fail", "winner", "hard work",
        "focus", "success", "grind", "jeetna", "taqat", "believe", "power", "impossible"
    ],
    "romantic": [
        "love", "pyaar", "dil", "ishq", "relationship", "together",
        "heart", "mohabbat", "shadi", "sweetheart"
    ],
    "comedy": [
        "joke", "funny", "laugh", "prank", "crazy", "comedy",
        "lmao", "lol", "hahaha", "hasna", "mazaak", "pagal"
    ],
}


def load_music_manifest() -> Dict[str, Any]:
    """Load the royalty-free music catalog manifest."""
    if not MANIFEST_PATH.exists():
        return {"tracks": []}
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def list_available_tracks() -> List[Dict[str, Any]]:
    """Return all available tracks with paths for UI selection."""
    manifest = load_music_manifest()
    results = []
    for t in manifest.get("tracks", []):
        track_path = TRACKS_DIR / t.get("filename", "")
        t_copy = dict(t)
        t_copy["file_exists"] = track_path.exists()
        t_copy["file_path"] = str(track_path)
        results.append(t_copy)
    return results


def get_track_for_mood(mood: Optional[str]) -> Optional[Dict[str, Any]]:
    """Return track dictionary matching mood, or None if mood is None."""
    if not mood:
        return None
    for t in list_available_tracks():
        if t.get("mood") == mood.lower() and t.get("file_exists"):
            return t
    return None


def get_track_by_id(track_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve specific track by its ID."""
    for t in list_available_tracks():
        if t.get("id") == track_id and t.get("file_exists"):
            return t
    return None


def detect_clip_mood(candidate: Dict[str, Any]) -> Tuple[Optional[str], str]:
    """Analyze transcript, word pacing, and pauses to determine if background music is called for.
    
    Returns:
        (mood_string_or_None, reason_string)
    """
    text = candidate.get("text", "").lower()
    words = candidate.get("words", [])
    duration = candidate.get("duration", 1.0)

    # 1. Check mood keywords
    matched_moods: Dict[str, List[str]] = {}
    for mood, kws in MOOD_KEYWORDS.items():
        hits = [kw for kw in kws if kw in text]
        if hits:
            matched_moods[mood] = hits

    # 2. Check pauses and speech pacing
    word_count = len(words) if words else len(text.split())
    wpm = (word_count / duration) * 60.0 if duration > 0 else 120.0

    # Emotional cue: Slower reflective pace (<120 WPM) or pauses + emotional keywords
    if "emotional" in matched_moods:
        hits_str = ", ".join(matched_moods["emotional"][:2])
        if wpm < 130:
            return "emotional", f"Emotional: reflective speech pace ({int(wpm)} wpm) + keyword '{hits_str}'"
        return "emotional", f"Emotional: keyword '{hits_str}'"

    # Motivational cue: energetic pace + motivational keywords
    if "motivational" in matched_moods:
        hits_str = ", ".join(matched_moods["motivational"][:2])
        return "motivational", f"Motivational: high-energy comeback theme + keyword '{hits_str}'"

    # Romantic cue
    if "romantic" in matched_moods:
        hits_str = ", ".join(matched_moods["romantic"][:2])
        return "romantic", f"Romantic: keyword '{hits_str}'"

    # Comedy cue: laughter/laughter tokens or comedy keywords
    if "comedy" in matched_moods:
        hits_str = ", ".join(matched_moods["comedy"][:2])
        return "comedy", f"Comedy: punchline/laughter timing + keyword '{hits_str}'"

    # Default: Do not force music on informational / standard speech
    return None, "Informational / neutral speech: no background music required"
