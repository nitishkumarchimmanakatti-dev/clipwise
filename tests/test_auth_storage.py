"""Tests for authentication and storage management in Clipwise v2."""

import pytest
import time
from pathlib import Path
from clipwise.auth import generate_session_token, verify_session_token
from clipwise.storage import clean_expired_originals, get_next_render_version, get_storage_stats


def test_auth_token_generation_and_verification(monkeypatch):
    monkeypatch.setattr("clipwise.auth.CLIPWISE_PASSWORD", "secret123")
    token = generate_session_token("secret123")
    assert verify_session_token(token) is True

    # Bad token
    assert verify_session_token("invalid_token") is False
    assert verify_session_token("12345:wrongsignature") is False

    # Empty password allows all (dev mode)
    monkeypatch.setattr("clipwise.auth.CLIPWISE_PASSWORD", "")
    assert verify_session_token(None) is True
    assert verify_session_token("any_string") is True


def test_get_next_render_version(tmp_path):
    # Empty dir starts at version 2
    assert get_next_render_version(tmp_path) == 2

    # If v2 already exists, increments to 3
    (tmp_path / "vid_v2_clip_01.mp4").touch()
    assert get_next_render_version(tmp_path) == 3


def test_clean_expired_originals(tmp_path, monkeypatch):
    monkeypatch.setattr("clipwise.storage.ORIGINALS_DIR", tmp_path)

    old_file = tmp_path / "old_video.mp4"
    old_file.touch()
    # Set mtime to 10 days ago
    ten_days_ago = time.time() - (10 * 86400)
    import os
    os.utime(str(old_file), (ten_days_ago, ten_days_ago))

    fresh_file = tmp_path / "fresh_video.mp4"
    fresh_file.touch()

    cleaned = clean_expired_originals(ttl_days=7)
    assert cleaned == 1
    assert not old_file.exists()
    assert fresh_file.exists()
