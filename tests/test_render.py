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

    # 3. Verify video dimensions using ffprobe
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "json",
        str(output_mp4)
    ]
    res = subprocess.run(probe_cmd, check=True, stdout=subprocess.PIPE, text=True)
    probe_data = json.loads(res.stdout)
    stream = probe_data["streams"][0]

    assert stream["width"] == 1080
    assert stream["height"] == 1920
