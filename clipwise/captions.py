"""Subtitle (.srt) generation and styling for YouTube Shorts."""

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


def create_srt_content(
    words: List[Dict[str, Any]],
    clip_start_offset: float = 0.0,
    words_per_subtitle: int = 4,
) -> str:
    """Generate SRT subtitle text from word-level timestamps relative to clip start.
    
    Groups words into short, energetic chunks (3-5 words) typical for YouTube Shorts.
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
        rel_end = max(rel_start + 0.3, chunk[-1]["end"] - clip_start_offset)
        
        start_ts = format_srt_timestamp(rel_start)
        end_ts = format_srt_timestamp(rel_end)
        
        text = " ".join(cw["word"] for cw in chunk).upper()  # All-caps is standard for viral Shorts
        
        srt_entries.append(f"{idx}\n{start_ts} --> {end_ts}\n{text}\n")

    return "\n".join(srt_entries)


def write_srt_file(
    words: List[Dict[str, Any]],
    output_srt_path: Path,
    clip_start_offset: float = 0.0,
    words_per_subtitle: int = 4,
) -> Path:
    """Write an .srt file to disk."""
    srt_content = create_srt_content(words, clip_start_offset, words_per_subtitle)
    output_srt_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)
    return output_srt_path
