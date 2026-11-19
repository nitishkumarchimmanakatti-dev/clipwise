"""Tests for ASS and SRT subtitle generation and layout."""

import pytest
from pathlib import Path
from clipwise.captions import (
    hex_to_ass_color,
    wrap_caption_lines,
    create_ass_content,
    create_srt_content,
    write_ass_file,
)


def test_hex_to_ass_color():
    # Warm gold: R=FF, G=D7, B=00 -> ASS &H0000D7FF
    assert hex_to_ass_color("#FFD700") == "&H0000D7FF"
    # Pure white
    assert hex_to_ass_color("#FFFFFF") == "&H00FFFFFF"
    # Electric yellow (#1BF7FF)
    assert hex_to_ass_color("#1BF7FF") == "&H00FFF71B"


def test_wrap_caption_lines():
    short = "SHORT HOOK"
    assert wrap_caption_lines(short, max_chars_per_line=32, max_lines=2) == "SHORT HOOK"

    long_sentence = "THIS IS A VERY LONG SENTENCE THAT EXCEEDS THE THIRTY TWO CHARACTER LIMIT ON A SINGLE LINE"
    wrapped = wrap_caption_lines(long_sentence, max_chars_per_line=32, max_lines=2)
    lines = wrapped.split("\\N")
    assert len(lines) <= 2
    for l in lines:
        assert len(l) <= 32


def test_devanagari_hindi_captions(tmp_path):
    mock_words = [
        {"word": "यह", "start": 0.5, "end": 0.8},
        {"word": "सबसे", "start": 0.9, "end": 1.2},
        {"word": "बड़ा", "start": 1.3, "end": 1.6},
        {"word": "रहस्य", "start": 1.7, "end": 2.2},
        {"word": "है!", "start": 2.3, "end": 2.7},
    ]
    ass_path = tmp_path / "hindi_test.ass"
    write_ass_file(mock_words, ass_path, clip_start_offset=0.0)
    assert ass_path.exists()
    content = ass_path.read_text(encoding="utf-8")
    assert "रहस्य" in content
    assert "PlayResX: 1080" in content
    assert "PlayResY: 1920" in content
    assert "MarginV" in content
