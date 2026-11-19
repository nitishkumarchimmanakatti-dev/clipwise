"""Subtitle (.srt and .ass) generation and viral styling for YouTube Shorts."""

from pathlib import Path
from typing import List, Dict, Any


def format_srt_timestamp(seconds: float) -> str:
    """Format float seconds into SRT timestamp string: HH:MM:SS,mmm."""
    if seconds < 0:
        seconds = 0.0

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        millis = 999

    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_ass_timestamp(seconds: float) -> str:
    """Format float seconds into ASS timestamp string: H:MM:SS.cc (centiseconds)."""
    if seconds < 0:
        seconds = 0.0

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        centis = 99

    return f"{hours:01d}:{minutes:02d}:{secs:02d}.{centis:02d}"


def create_srt_content(
    words: List[Dict[str, Any]],
    clip_start_offset: float = 0.0,
    words_per_subtitle: int = 3,
) -> str:
    """Generate SRT subtitle text from word-level timestamps relative to clip start.
    
    Groups words into short, energetic chunks (2-3 words) typical for YouTube Shorts.
    """
    if not words:
        return ""

    subtitles = []
    current_chunk: List[Dict[str, Any]] = []

    for w in words:
        current_chunk.append(w)
        if len(current_chunk) >= words_per_subtitle:
            subtitles.append(current_chunk)
            current_chunk = []

    if current_chunk:
        subtitles.append(current_chunk)

    srt_entries: List[str] = []
    for idx, chunk in enumerate(subtitles, start=1):
        rel_start = max(0.0, chunk[0]["start"] - clip_start_offset)
        rel_end = max(rel_start + 0.35, chunk[-1]["end"] - clip_start_offset)
        
        start_ts = format_srt_timestamp(rel_start)
        end_ts = format_srt_timestamp(rel_end)
        
        text = " ".join(cw["word"] for cw in chunk).upper()
        
        srt_entries.append(f"{idx}\n{start_ts} --> {end_ts}\n{text}\n")

    return "\n".join(srt_entries)


def write_srt_file(
    words: List[Dict[str, Any]],
    output_srt_path: Path,
    clip_start_offset: float = 0.0,
    words_per_subtitle: int = 3,
) -> Path:
    """Write an .srt file to disk."""
    srt_content = create_srt_content(words, clip_start_offset, words_per_subtitle)
    output_srt_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)
    return output_srt_path


def create_ass_content(
    words: List[Dict[str, Any]],
    clip_start_offset: float = 0.0,
    words_per_subtitle: int = 3,
    mode: str = "blur",
) -> str:
    """Generate high-retention, stylish ASS subtitle file.
    
    Positioned in the lower blurred region for 'blur' mode so the main 16:9
    video content remains 100% visible and unobstructed.
    """
    # In 1080x1920 canvas:
    # 16:9 video is centered vertically at Y = 656 to 1264.
    # Bottom blur spans Y = 1264 to 1920 (height = 656px).
    # MarginV=460 places captions centered at Y ≈ 1400-1460 (in the blur region),
    # ~140px below the video frame and ~460px above bottom screen edge.
    margin_v = 460 if mode == "blur" else 280

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ViralShort,Arial,56,&H001BF7FF,&H000000FF,&H00000000,&HA0000000,-1,0,0,0,100,100,1,0,1,6,3,2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    if not words:
        return header

    subtitles = []
    current_chunk: List[Dict[str, Any]] = []

    for w in words:
        current_chunk.append(w)
        if len(current_chunk) >= words_per_subtitle:
            subtitles.append(current_chunk)
            current_chunk = []

    if current_chunk:
        subtitles.append(current_chunk)

    dialogue_lines: List[str] = []
    for chunk in subtitles:
        rel_start = max(0.0, chunk[0]["start"] - clip_start_offset)
        rel_end = max(rel_start + 0.35, chunk[-1]["end"] - clip_start_offset)

        start_ts = format_ass_timestamp(rel_start)
        end_ts = format_ass_timestamp(rel_end)

        text = " ".join(cw["word"] for cw in chunk).upper()
        # Clean any special ASS brackets or backslashes
        text = text.replace("{", "(").replace("}", ")").replace("\\", "/")
        dialogue_lines.append(f"Dialogue: 0,{start_ts},{end_ts},ViralShort,,0,0,0,,{text}")

    return header + "\n".join(dialogue_lines) + "\n"


def write_ass_file(
    words: List[Dict[str, Any]],
    output_ass_path: Path,
    clip_start_offset: float = 0.0,
    words_per_subtitle: int = 3,
    mode: str = "blur",
) -> Path:
    """Write an .ass subtitle file with viral typography and blur-zone positioning."""
    ass_content = create_ass_content(words, clip_start_offset, words_per_subtitle, mode)
    output_ass_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_ass_path, "w", encoding="utf-8") as f:
        f.write(ass_content)
    return output_ass_path
