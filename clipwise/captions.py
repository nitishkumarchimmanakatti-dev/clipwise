"""Subtitle (.srt and .ass) generation and viral styling for YouTube Shorts."""

from pathlib import Path
from typing import List, Dict, Any
from clipwise.config import DEFAULT_CAPTION_COLOR


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


def hex_to_ass_color(hex_color: str) -> str:
    """Convert #RRGGBB or #RGB to ASS format &H00BBGGRR (BGR order)."""
    clean = (hex_color or "").strip().lstrip("#")
    if len(clean) == 3:
        clean = "".join(c * 2 for c in clean)
    if len(clean) != 6:
        clean = "FFD700"  # default warm gold (#FFD700)
    r = clean[0:2]
    g = clean[2:4]
    b = clean[4:6]
    return f"&H00{b.upper()}{g.upper()}{r.upper()}"


def wrap_caption_lines(text: str, max_chars_per_line: int = 32, max_lines: int = 2) -> str:
    """Wrap caption text into maximum 2 lines of at most 32 characters each."""
    words = text.split()
    if not words:
        return ""
    lines = []
    current_line: List[str] = []
    current_len = 0
    for w in words:
        w_len = len(w)
        if current_line and (current_len + 1 + w_len) > max_chars_per_line:
            lines.append(" ".join(current_line))
            current_line = [w]
            current_len = w_len
            if len(lines) >= max_lines - 1:
                break
        else:
            current_line.append(w)
            current_len += (1 if len(current_line) > 1 else 0) + w_len
    if current_line and len(lines) < max_lines:
        lines.append(" ".join(current_line))
    return "\\N".join(lines[:max_lines])


def create_srt_content(
    words: List[Dict[str, Any]],
    clip_start_offset: float = 0.0,
    words_per_subtitle: int = 3,
) -> str:
    """Generate standard SRT subtitle text from word-level timestamps relative to clip start."""
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
    caption_color: str = DEFAULT_CAPTION_COLOR,
) -> str:
    """Generate high-retention, stylish ASS subtitle file.
    
    Positioned strictly in the lower blurred region (Y ≈ 1400 to 1700) with
    at least 150px clearance from the bottom edge of the sharp 16:9 video frame.
    Supports Noto Sans Devanagari for Hindi/Hinglish rendering without blank boxes.
    """
    margin_v = 460 if mode == "blur" else 280
    primary_color_ass = hex_to_ass_color(caption_color)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ViralShort,Noto Sans,56,{primary_color_ass},&H000000FF,&H00000000,&HA0000000,-1,0,0,0,100,100,1,0,1,6,3,2,60,60,{margin_v},1

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

        raw_text = " ".join(cw["word"] for cw in chunk).upper()
        # Clean special ASS control characters
        raw_text = raw_text.replace("{", "(").replace("}", ")").replace("\\", "/")
        # Wrap into at most 2 lines, max 32 chars each
        wrapped = wrap_caption_lines(raw_text, max_chars_per_line=32, max_lines=2)

        dialogue_lines.append(f"Dialogue: 0,{start_ts},{end_ts},ViralShort,,0,0,0,,{wrapped}")

    return header + "\n".join(dialogue_lines) + "\n"


def write_ass_file(
    words: List[Dict[str, Any]],
    output_ass_path: Path,
    clip_start_offset: float = 0.0,
    words_per_subtitle: int = 3,
    mode: str = "blur",
    caption_color: str = DEFAULT_CAPTION_COLOR,
) -> Path:
    """Write an .ass subtitle file with viral typography and blur-zone positioning."""
    ass_content = create_ass_content(
        words=words,
        clip_start_offset=clip_start_offset,
        words_per_subtitle=words_per_subtitle,
        mode=mode,
        caption_color=caption_color,
    )
    output_ass_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_ass_path, "w", encoding="utf-8") as f:
        f.write(ass_content)
    return output_ass_path
