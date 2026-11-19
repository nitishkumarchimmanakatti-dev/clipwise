"""End-to-end test for clip cutting, vertical 9:16 reformatting, and subtitle burn-in."""

import subprocess
import json
from pathlib import Path
from clipwise.render import render_clip


def test_render_clip_end_to_end(tmp_path):
    source_mp4 = tmp_path / "synthetic_source.mp4"
    output_mp4 = tmp_path / "clip_01.mp4"
    output_srt = tmp_path / "clip_01.srt"

    # 1. Generate a 5-second synthetic test video with audio using ffmpeg
    gen_cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=5:size=1280x720:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
        "-c:v", "libx264", "-c:a", "aac",
        str(source_mp4)
    ]
    subprocess.run(gen_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert source_mp4.exists()

    candidate = {
        "start": 0.5,
        "end": 3.5,
        "duration": 3.0,
        "words": [
            {"word": "Welcome", "start": 0.5, "end": 1.0, "probability": 1.0},
            {"word": "to", "start": 1.1, "end": 1.4, "probability": 1.0},
            {"word": "Clipwise", "start": 1.5, "end": 2.2, "probability": 1.0},
            {"word": "Shorts!", "start": 2.3, "end": 3.4, "probability": 1.0},
        ],
    }

    # 2. Render the clip in vertical mode (blurred background)
    rendered_file = render_clip(
        source_video=source_mp4,
        candidate=candidate,
        output_mp4=output_mp4,
        output_srt=output_srt,
        mode="blur",
        burn_captions=True,
        force=True,
    )

    assert rendered_file.exists()
    assert output_srt.exists()

    # Verify that .ass was generated
    output_ass = output_srt.with_suffix(".ass")
    assert output_ass.exists()


def test_render_clip_with_situational_music(tmp_path):
    source_mp4 = tmp_path / "src.mp4"
    music_mp3 = tmp_path / "bg_music.mp3"
    out_mp4 = tmp_path / "clip_music.mp4"
    out_srt = tmp_path / "clip_music.srt"

    # Synthetic source video and music track
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=4:size=1280x720:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
        "-c:v", "libx264", "-c:a", "aac", str(source_mp4)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "sine=frequency=220:duration=10",
        "-c:a", "libmp3lame", str(music_mp3)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    candidate = {
        "start": 0.0,
        "end": 3.0,
        "duration": 3.0,
        "words": [{"word": "TEST", "start": 0.5, "end": 2.0}],
    }

    mock_track = {
        "id": "test_track",
        "name": "Test Track",
        "file_path": str(music_mp3),
        "license": "CC0",
    }

    res = render_clip(
        source_video=source_mp4,
        candidate=candidate,
        output_mp4=out_mp4,
        output_srt=out_srt,
        mode="blur",
        music_track=mock_track,
        force=True,
    )
    assert res.exists()
    assert res.stat().st_size > 0

    # 3. Verify video dimensions using ffprobe
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "json",
        str(out_mp4)
    ]
    res_probe = subprocess.run(probe_cmd, check=True, stdout=subprocess.PIPE, text=True)
    probe_data = json.loads(res_probe.stdout)
    stream = probe_data["streams"][0]

    assert stream["width"] == 1080
    assert stream["height"] == 1920
