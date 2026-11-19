"""Tests for situational background music detection and manifest."""

import pytest
from pathlib import Path
from clipwise.music import (
    detect_clip_mood,
    get_track_for_mood,
    list_available_tracks,
    get_track_by_id,
)


def test_list_available_tracks():
    tracks = list_available_tracks()
    assert len(tracks) >= 4
    moods = {t["mood"] for t in tracks}
    assert "emotional" in moods
    assert "motivational" in moods
    assert "romantic" in moods
    assert "comedy" in moods


def test_detect_clip_mood_neutral_speech():
    # Pure informational tech discussion -> NO music
    candidate = {
        "text": "The Python interpreter reads code line by line and converts it into bytecode.",
        "words": [],
        "duration": 25.0,
    }
    mood, reason = detect_clip_mood(candidate)
    assert mood is None
    assert "no background music" in reason.lower()


def test_detect_clip_mood_emotional():
    # Emotional keywords + slower speech
    candidate = {
        "text": "I really miss my mother and the struggle she faced in life.",
        "words": [
            {"word": "I", "start": 0.0, "end": 0.5},
            {"word": "miss", "start": 1.0, "end": 1.5},
            {"word": "mother", "start": 2.0, "end": 2.5},
            {"word": "struggle", "start": 3.0, "end": 4.0},
        ],
        "duration": 30.0,
    }
    mood, reason = detect_clip_mood(candidate)
    assert mood == "emotional"
    assert "miss" in reason or "mother" in reason


def test_detect_clip_mood_motivational():
    # Motivational comeback
    candidate = {
        "text": "Never give up because winners fail but they get back up!",
        "words": [],
        "duration": 20.0,
    }
    mood, reason = detect_clip_mood(candidate)
    assert mood == "motivational"
    assert "never give up" in reason or "motivational" in reason.lower()


def test_get_track_for_mood():
    track = get_track_for_mood("emotional")
    assert track is not None
    assert track["mood"] == "emotional"
    assert Path(track["file_path"]).exists()

    no_track = get_track_for_mood(None)
    assert no_track is None
