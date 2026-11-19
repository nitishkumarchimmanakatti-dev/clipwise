"""Video rendering and 9:16 vertical reformatting using ffmpeg."""

from pathlib import Path
from typing import Dict, Any, Optional
import subprocess

from clipwise.config import (
    ensure_ffmpeg,
    get_ffmpeg_path,
    has_subtitles_filter,
    TARGET_WIDTH,
    TARGET_HEIGHT,
    DEFAULT_RENDER_MODE,
)
from clipwise.captions import write_srt_file, write_ass_file


def render_clip(
    source_video: Path,
    candidate: Dict[str, Any],
    output_mp4: Path,
    output_srt: Path,
    mode: str = DEFAULT_RENDER_MODE,
    burn_captions: bool = True,
    force: bool = False,
) -> Path:
    """Cut, reformat to 9:16 vertical (1080x1920), and provide subtitles.
    
    Args:
        source_video: path to the downloaded source mp4
        candidate: dict with 'start', 'end', 'duration', 'words'
        output_mp4: path where the rendered short will be saved
        output_srt: path where the .srt file will be saved
        mode: 'blur' (blurred background overlay) or 'crop' (center 9:16 crop)
        burn_captions: whether to burn subtitles directly into video frames if supported
        force: overwrite existing clip if True
    """
    ensure_ffmpeg()
    ffmpeg_bin = get_ffmpeg_path()

    if output_mp4.exists() and not force:
        return output_mp4

    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    start_time = candidate["start"]
    end_time = candidate["end"]

    # 1. Write the .srt file (for downloads) and .ass file (for viral styled rendering)
    write_srt_file(
        words=candidate.get("words", []),
        output_srt_path=output_srt,
        clip_start_offset=start_time,
        words_per_subtitle=3,
    )
    output_ass = output_srt.with_suffix(".ass")
    write_ass_file(
        words=candidate.get("words", []),
        output_ass_path=output_ass,
        clip_start_offset=start_time,
        words_per_subtitle=3,
        mode=mode,
    )

    # 2. Build the visual 9:16 vertical filter
    if mode == "crop":
        base_filter = (
            f"[0:v]scale=-1:{TARGET_HEIGHT},"
            f"crop={TARGET_WIDTH}:{TARGET_HEIGHT}:(in_w-{TARGET_WIDTH})/2:0[v0]"
        )
    else:
        # Default 'blur': Blurred background with centered sharp foreground
        base_filter = (
            f"[0:v]scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={TARGET_WIDTH}:{TARGET_HEIGHT},boxblur=25:5[bg];"
            f"[0:v]scale={TARGET_WIDTH}:-2[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[v0]"
        )

    supports_burn = has_subtitles_filter()
    has_ass_content = output_ass.exists() and output_ass.stat().st_size > 0

    if burn_captions and supports_burn and has_ass_content:
        # Burn in stylish captions placed in the lower blur zone (video remains 100% visible)
        clean_ass_path = str(output_ass.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        filter_complex = f"{base_filter};[v0]ass='{clean_ass_path}'[vout]"
        
        cmd = [
            ffmpeg_bin, "-y",
            "-ss", str(start_time),
            "-to", str(end_time),
            "-i", str(source_video),
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-x264opts", "threads=2:lookahead-threads=1",
            "-preset", "ultrafast",
            "-crf", "24",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            str(output_mp4),
        ]
    else:
        # Reformat 9:16 and embed soft subtitle track (mov_text) for universal player compatibility
        filter_complex = base_filter.replace("[v0]", "[vout]")
        cmd = [
            ffmpeg_bin, "-y",
            "-ss", str(start_time),
            "-to", str(end_time),
            "-i", str(source_video),
        ]
        if has_srt_content:
            cmd.extend(["-i", str(output_srt)])
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "0:a?",
        ])
        if has_srt_content:
            cmd.extend([
                "-map", "1:s?",
                "-c:s", "mov_text",
            ])
        cmd.extend([
            "-c:v", "libx264",
            "-x264opts", "threads=2:lookahead-threads=1",
            "-preset", "ultrafast",
            "-crf", "24",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            str(output_mp4),
        ])

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg rendering failed: {result.stderr}")

    return output_mp4
