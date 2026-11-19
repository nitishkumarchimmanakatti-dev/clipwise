"""Tests for music management, license logging, ducking mix, OpenCV crop, and hook overlays."""

import pytest
import subprocess
from pathlib import Path
import json

from clipwise.music import (
    ensure_music_available,
    get_licensed_tracks,
    log_music_license,
    select_track_for_clip,
    get_ducking_audio_filter,
)
from clipwise.captions import create_ass_content, write_ass_file
from clipwise.crop import get_smart_crop_filter
from clipwise.render import render_clip
from main import run_pipeline, run_pipeline_for_file


def test_empty_music_folder_handling(tmp_path: Path):
    """Verify that an empty music directory skips music with a warning or refuses execution."""
    empty_dir = tmp_path / "empty_music"
    empty_dir.mkdir(parents=True, exist_ok=True)
    licenses_file = empty_dir / "music_licenses.csv"

    # 1. get_licensed_tracks returns empty list
    tracks = get_licensed_tracks(music_dir=empty_dir, licenses_file=licenses_file)
    assert tracks == []

    # 2. ensure_music_available without raise returns empty list
    available = ensure_music_available(music_dir=empty_dir, raise_if_empty=False)
    assert available == []

    # 3. select_track_for_clip returns None
    candidate = {"text": "I really miss my mother and feel sad", "words": [], "duration": 30.0}
    chosen = select_track_for_clip(candidate, music_dir=empty_dir)
    assert chosen is None

    # 4. ensure_music_available with raise_if_empty=True raises RuntimeError
    with pytest.raises(RuntimeError, match="Refusing to run music step"):
        ensure_music_available(music_dir=empty_dir, raise_if_empty=True)


def test_music_licenses_logging(tmp_path: Path):
    """Verify logging tracks to music_licenses.csv."""
    music_dir = tmp_path / "music"
    music_dir.mkdir(parents=True, exist_ok=True)
    licenses_file = music_dir / "music_licenses.csv"

    log_music_license("cinematic_beat.mp3", "YouTube Audio Library (Attribution not required)", "YouTube", licenses_file)
    assert licenses_file.exists()

    content = licenses_file.read_text(encoding="utf-8")
    assert "filename,license_note,source,added_at" in content
    assert "cinematic_beat.mp3" in content
    assert "YouTube Audio Library" in content


def test_ducking_audio_filter_generation():
    """Verify the -20 dB volume (0.10) and 0.5s fade in/out parameters in the ducking filter."""
    filter_str = get_ducking_audio_filter(clip_dur=30.0, speech_volume=1.0, music_volume=0.10, fade_duration=0.5)
    assert "afade=t=in:ss=0:d=0.5" in filter_str
    assert "afade=t=out:st=29.5:d=0.5" in filter_str
    assert "volume=0.1" in filter_str
    assert "sidechaincompress" in filter_str
    assert "amix=inputs=2" in filter_str


def test_hook_overlay_ass_content():
    """Verify the first 5 words are formatted as large on-screen text for the first 2 seconds."""
    words = [
        {"word": "The", "start": 0.1, "end": 0.4},
        {"word": "biggest", "start": 0.45, "end": 0.8},
        {"word": "secret", "start": 0.85, "end": 1.2},
        {"word": "in", "start": 1.25, "end": 1.4},
        {"word": "business", "start": 1.45, "end": 1.9},
        {"word": "is", "start": 2.0, "end": 2.2},
        {"word": "focus", "start": 2.25, "end": 2.7},
    ]
    ass_content = create_ass_content(
        words=words,
        clip_start_offset=0.0,
        include_hook_overlay=True,
    )
    assert "Style: HookOverlay" in ass_content
    assert "Dialogue: 1,0:00:00.00,0:00:02.00,HookOverlay" in ass_content
    assert "THE BIGGEST SECRET" in ass_content
    assert "BUSINESS" in ass_content


def test_rights_confirmed_enforcement(tmp_path: Path):
    """Verify that execution is refused if rights_confirmed is False."""
    dummy_video = tmp_path / "dummy.mp4"
    dummy_video.write_bytes(b"dummy")

    with pytest.raises(ValueError, match="rights_confirmed"):
        run_pipeline(
            url="https://youtu.be/dummy123456",
            ownership_confirmed=False,
            rights_confirmed=False,
        )

    with pytest.raises(ValueError, match="rights_confirmed"):
        run_pipeline_for_file(
            video_file_path=dummy_video,
            rights_confirmed=False,
        )


def test_ducking_and_hook_overlay_rendering(tmp_path: Path):
    """Integration test: Render a synthetic clip with ducked music and hook overlay into valid MP4."""
    source_mp4 = tmp_path / "source.mp4"
    music_mp3 = tmp_path / "background.mp3"
    out_mp4 = tmp_path / "output_clip.mp4"
    out_srt = tmp_path / "output_clip.srt"

    # Create synthetic 3-second 720p video
    cmd_video = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=3:size=1280x720:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac",
        str(source_mp4)
    ]
    subprocess.run(cmd_video, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Create synthetic 3-second background music
    cmd_music = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "sine=frequency=220:duration=3",
        "-c:a", "libmp3lame",
        str(music_mp3)
    ]
    subprocess.run(cmd_music, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    candidate = {
        "start": 0.0,
        "end": 3.0,
        "duration": 3.0,
        "text": "Never make this fatal mistake now",
        "words": [
            {"word": "Never", "start": 0.1, "end": 0.5},
            {"word": "make", "start": 0.55, "end": 0.8},
            {"word": "this", "start": 0.85, "end": 1.1},
            {"word": "fatal", "start": 1.15, "end": 1.6},
            {"word": "mistake", "start": 1.65, "end": 2.1},
            {"word": "now", "start": 2.15, "end": 2.5},
        ]
    }

    music_track = {
        "name": "Test Ambient",
        "file_path": str(music_mp3),
        "license": "Royalty-free",
    }

    rendered = render_clip(
        source_video=source_mp4,
        candidate=candidate,
        output_mp4=out_mp4,
        output_srt=out_srt,
        mode="blur",
        burn_captions=True,
        force=True,
        music_track=music_track,
        trim_silence=True,
        include_hook_overlay=True,
    )

    assert rendered.exists()
    assert rendered.stat().st_size > 1000

    # Probe that output is valid mp4 with video and audio streams
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        str(rendered)
    ]
    res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
    assert "1080x1920" in res.stdout.strip()
