import pytest
import os
import csv
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from clipwise.review import log_pipeline_stage
from clipwise.app import app
import clipwise.config as config
import main

client = TestClient(app)

def test_log_pipeline_stage():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_log_csv = Path(tmpdir) / "test_clipwise_log.csv"
        
        # Log 2 stages
        log_pipeline_stage("video_123", "download", "success", 2.34, "Downloaded test.mp4", test_log_csv)
        log_pipeline_stage("video_123", "transcribe", "failed", 1.12, "No speech detected", test_log_csv)
        
        assert test_log_csv.exists()
        with open(test_log_csv, "r", encoding="utf-8") as f:
            reader = list(csv.reader(f))
            assert len(reader) == 3 # Header + 2 rows
            assert reader[0] == ["timestamp", "video_id", "stage", "status", "duration_sec", "details"]
            assert reader[1][1] == "video_123"
            assert reader[1][2] == "download"
            assert reader[1][3] == "success"
            assert reader[1][4] == "2.34"
            assert reader[2][2] == "transcribe"
            assert reader[2][3] == "failed"

def test_no_speech_detection_raises_informative_error(monkeypatch):
    # Mock download_video and transcribe_audio to return empty transcript
    fake_video = Path("/fake/video.mp4")
    fake_audio = Path("/fake/audio.wav")
    fake_meta = {"title": "Test Title", "duration": 30}
    monkeypatch.setattr(main, "download_video", lambda *args, **kwargs: (fake_video, fake_audio, fake_meta))
    monkeypatch.setattr(main, "transcribe_audio", lambda *args, **kwargs: {"segments": [], "full_text": ""})
    
    with pytest.raises(ValueError) as excinfo:
        main.run_pipeline("https://youtube.com/watch?v=dummy", rights_confirmed=True)
    assert "No speech detected in this video" in str(excinfo.value)
    assert "Clipwise relies on spoken words" in str(excinfo.value)

def test_api_config_endpoint():
    res = client.get("/api/config")
    assert res.status_code == 200
    data = res.json()
    assert "enable_youtube" in data
    assert "max_upload_size_mb" in data
    assert "default_caption_color" in data

def test_api_generate_blocked_when_youtube_disabled(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_YOUTUBE_URL", False)
    res = client.post("/api/generate", json={
        "url": "https://www.youtube.com/watch?v=test",
        "ownership_confirmed": True
    })
    assert res.status_code == 403
    assert "YouTube URL processing is disabled" in res.json()["detail"]

def test_api_upload_refused_without_rights():
    with tempfile.NamedTemporaryFile(suffix=".mp4") as tmp:
        tmp.write(b"fake video data")
        tmp.seek(0)
        res = client.post(
            "/api/upload",
            files={"file": ("test.mp4", tmp, "video/mp4")},
            data={"rights_confirmed": "false"}
        )
        assert res.status_code == 400
        assert "rights confirmation required" in res.json()["detail"].lower()
