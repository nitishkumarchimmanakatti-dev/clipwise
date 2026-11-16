"""Tests for URL validation and YouTube download paths."""

import pytest
from clipwise.download import extract_video_id, validate_youtube_url


def test_extract_video_id_standard_url():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert extract_video_id(url) == "dQw4w9WgXcQ"


def test_extract_video_id_short_url():
    url = "https://youtu.be/dQw4w9WgXcQ?t=10"
    assert extract_video_id(url) == "dQw4w9WgXcQ"


def test_extract_video_id_shorts_url():
    url = "https://www.youtube.com/shorts/dQw4w9WgXcQ"
    assert extract_video_id(url) == "dQw4w9WgXcQ"


def test_validate_youtube_url_valid():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert validate_youtube_url(url) == "dQw4w9WgXcQ"


def test_validate_youtube_url_rejects_playlist():
    playlist_url = "https://www.youtube.com/playlist?list=PL1234567890"
    with pytest.raises(ValueError, match="Playlist URLs are not supported"):
        validate_youtube_url(playlist_url)


def test_validate_youtube_url_rejects_non_youtube():
    bad_url = "https://vimeo.com/12345678"
    with pytest.raises(ValueError, match="URL domain is not YouTube"):
        validate_youtube_url(bad_url)


def test_validate_youtube_url_empty():
    with pytest.raises(ValueError, match="empty"):
        validate_youtube_url("")
