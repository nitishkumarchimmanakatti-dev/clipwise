"""Tests for review sheet creation, state updates, and log tracking."""

import csv
from clipwise.review import init_review_sheet, set_clip_status, load_review_sheet


def test_review_sheet_lifecycle(tmp_path):
    mock_clips = [
        {"clip_id": "clip_01", "start": 10.0, "end": 40.0, "duration": 30.0, "hook_score": 8.5, "title": "First Hook"},
        {"clip_id": "clip_02", "start": 50.0, "end": 85.0, "duration": 35.0, "hook_score": 7.2, "title": "Second Hook"},
    ]

    # Initialize review.csv
    csv_file = init_review_sheet(tmp_path, mock_clips)
    assert csv_file.exists()

    rows = load_review_sheet(tmp_path)
    assert len(rows) == 2
    assert rows[0]["clip_id"] == "clip_01"
    assert rows[0]["status"] == "pending"
    assert rows[1]["status"] == "pending"

    # Manually modify status for clip_01
    rows[0]["status"] = "approved"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    # Re-running init_review_sheet should preserve approved status
    init_review_sheet(tmp_path, mock_clips)
    reloaded = load_review_sheet(tmp_path)
    assert reloaded[0]["status"] == "approved"
    assert reloaded[1]["status"] == "pending"
