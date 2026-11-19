"""Unit and integration tests for YouTube Data API v3 upload automation."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from clipwise.app import app
from clipwise.youtube_upload import (
    is_youtube_configured,
    check_channel_auth_status,
    upload_clip_to_youtube,
    save_client_secret_file,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_youtube_status_unconfigured(monkeypatch, tmp_path):
    monkeypatch.delenv("YOUTUBE_CLIENT_ID", raising=False)
    monkeypatch.delenv("YOUTUBE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("YOUTUBE_REFRESH_TOKEN", raising=False)

    status = check_channel_auth_status()
    assert isinstance(status, dict)
    assert status.get("authenticated") is False


def test_upload_clip_missing_file():
    with pytest.raises(FileNotFoundError):
        upload_clip_to_youtube(
            video_path=Path("/non/existent/path/clip.mp4"),
            title="Test Short",
            description="Testing shorts",
        )


def test_upload_clip_successful_mock(tmp_path):
    fake_video = tmp_path / "clip_01.mp4"
    fake_video.write_bytes(b"dummy mp4 video bytes")

    mock_service = MagicMock()
    mock_insert = MagicMock()
    mock_insert.next_chunk.return_value = (None, {"id": "mock_yt_12345"})
    mock_service.videos().insert.return_value = mock_insert

    with patch("clipwise.youtube_upload.get_youtube_service", return_value=mock_service):
        result = upload_clip_to_youtube(
            video_path=fake_video,
            title="Incredible AI Breakthrough!",
            description="Learn how AI is changing everything.",
            tags=["AI", "Tech"],
            privacy_status="public",
        )

        assert result["video_id"] == "mock_yt_12345"
        assert result["url"] == "https://youtube.com/shorts/mock_yt_12345"
        assert "#Shorts" in result["title"]
        assert result["privacy"] == "public"
        assert result["status"] == "uploaded"

        # Verify insert arguments
        call_kwargs = mock_service.videos().insert.call_args[1]
        body = call_kwargs["body"]
        assert body["snippet"]["categoryId"] == "22"
        assert body["status"]["privacyStatus"] == "public"
        assert body["status"]["selfDeclaredMadeForKids"] is False


def test_api_youtube_status_endpoint(client):
    res = client.get("/api/youtube/status")
    assert res.status_code == 200
    data = res.json()
    assert "authenticated" in data


def test_api_youtube_save_credentials(client, tmp_path, monkeypatch):
    test_json = '{"web": {"client_id": "test_id.apps.googleusercontent.com", "client_secret": "test_sec"}}'
    
    with patch("clipwise.app.save_client_secret_file") as mock_save:
        res = client.post("/api/youtube/auth/credentials", json={"credentials_json": test_json})
        assert res.status_code == 200
        assert res.json()["status"] == "ok"
        mock_save.assert_called_once_with(test_json)


def test_api_youtube_upload_missing_clip(client):
    res = client.post("/api/youtube/upload", json={
        "video_id": "non_existent_vid",
        "clip_id": "clip_99",
        "title": "Test Title"
    })
    assert res.status_code == 404
