"""Video rendering, 9:16 vertical reformatting, subtitle burning, and situational music ducking."""

from pathlib import Path
from typing import Dict, Any, Optional
import subprocess
import logging

from clipwise.config import (
    ensure_ffmpeg,
    get_ffmpeg_path,
    has_subtitles_filter,
    TARGET_WIDTH,
    TARGET_HEIGHT,
    DEFAULT_RENDER_MODE,
    DEFAULT_CAPTION_COLOR,
)
from clipwise.captions import write_srt_file, write_ass_file
from clipwise.crop import get_smart_crop_filter
from clipwise.music import get_ducking_audio_filter

logger = logging.getLogger("clipwise.render")


def render_clip(
    source_video: Path,
    candidate: Dict[str, Any],
    output_mp4: Path,
    output_srt: Path,
    mode: str = DEFAULT_RENDER_MODE,
    burn_captions: bool = True,
    force: bool = False,
    caption_color: str = DEFAULT_CAPTION_COLOR,
    music_track: Optional[Dict[str, Any]] = None,
    trim_silence: bool = True,
    include_hook_overlay: bool = True,
) -> Path:
    """Cut, reformat to 9:16 vertical (1080x1920), burn subtitles in bottom blur band,
    overlay the first 5 words as large hook text for the first 2 seconds,
    and apply background music at -20 dB with sidechain audio ducking and 0.5s fades.
    """
    ensure_ffmpeg()
    ffmpeg_bin = get_ffmpeg_path()

    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    start_time = candidate["start"]
    end_time = candidate["end"]
    clip_dur = max(1.0, round(end_time - start_time, 2))

    # 1. Write the .srt file (for downloads) and .ass file (for viral styled rendering + hook card)
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
        caption_color=caption_color,
        include_hook_overlay=include_hook_overlay,
    )

    # Only skip rendering if output_mp4 exists AND output_ass exists AND not force
    if output_mp4.exists() and output_ass.exists() and not force:
        return output_mp4

    # 2. Build the visual 9:16 vertical filter
    base_video_filter = None
    if mode == "crop":
        # Attempt smart OpenCV face-centered tracking crop
        smart_crop_str, has_face = get_smart_crop_filter(
            video_path=source_video,
            start_time=start_time,
            end_time=end_time,
            target_width=TARGET_WIDTH,
            target_height=TARGET_HEIGHT,
        )
        if has_face:
            base_video_filter = smart_crop_str
        else:
            # Fallback to blurred background padding when no face is found
            logger.info("No face detected in talking-head crop mode; falling back to blurred background padding.")

    if not base_video_filter:
        # Default 'blur': Blurred background with centered sharp foreground (1080x608)
        base_video_filter = (
            f"[0:v]scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={TARGET_WIDTH}:{TARGET_HEIGHT},boxblur=25:5[bg];"
            f"[0:v]scale={TARGET_WIDTH}:-2[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[v0]"
        )

    supports_burn = has_subtitles_filter()
    has_ass_content = output_ass.exists() and output_ass.stat().st_size > 0

    if burn_captions and supports_burn and has_ass_content:
        clean_ass_path = str(output_ass.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        v_filter = f"{base_video_filter};[v0]ass='{clean_ass_path}'[vout]"
    else:
        v_filter = base_video_filter.replace("[v0]", "[vout]")

    # 3. Check Background Music with Sidechain Audio Ducking
    has_valid_music = False
    music_file_path = None
    if music_track and music_track.get("file_path"):
        p = Path(music_track["file_path"])
        if p.exists() and p.stat().st_size > 0:
            has_valid_music = True
            music_file_path = str(p.resolve())

    cmd = [
        ffmpeg_bin, "-y",
        "-ss", str(start_time),
        "-to", str(end_time),
        "-i", str(source_video),
    ]

    # Silence trimming filter component (>0.6s dead air removal)
    silence_filter = "silenceremove=stop_periods=-1:stop_duration=0.6:stop_threshold=-35dB:detection=rms," if trim_silence else ""

    if has_valid_music:
        cmd.extend([
            "-stream_loop", "-1",
            "-i", music_file_path,
        ])
        fade_out_start = max(0.1, round(clip_dur - 0.5, 2))
        # Speech + sidechain ducked music filter (-20 dB volume=0.10, 0.5s fade in/out)
        a_filter = (
            f"[0:a]{silence_filter}volume=1.0[speech];"
            f"[1:a]afade=t=in:ss=0:d=0.5,afade=t=out:st={fade_out_start}:d=0.5,volume=0.10[music];"
            f"[music][speech]sidechaincompress=threshold=0.08:ratio=6:attack=50:release=350[ducked_music];"
            f"[speech][ducked_music]amix=inputs=2:duration=first[aout]"
        )
        full_filter = f"{v_filter};{a_filter}"
        cmd.extend([
            "-filter_complex", full_filter,
            "-map", "[vout]",
            "-map", "[aout]",
        ])
    else:
        if trim_silence:
            full_filter = f"{v_filter};[0:a]{silence_filter}volume=1.0[aout]"
            cmd.extend([
                "-filter_complex", full_filter,
                "-map", "[vout]",
                "-map", "[aout]",
            ])
        else:
            cmd.extend([
                "-filter_complex", v_filter,
                "-map", "[vout]",
                "-map", "0:a?",
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
