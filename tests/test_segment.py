"""Tests for candidate segment generation and sentence boundary alignment."""

from clipwise.segment import extract_sentences, generate_candidate_segments, filter_overlapping_candidates


def test_extract_sentences():
    mock_segments = [
        {
            "id": 1,
            "start": 0.0,
            "end": 4.0,
            "text": "Hello world! This is Clipwise.",
            "words": [
                {"word": "Hello", "start": 0.0, "end": 0.5, "probability": 0.99},
                {"word": "world!", "start": 0.6, "end": 1.2, "probability": 0.99},
                {"word": "This", "start": 1.5, "end": 2.0, "probability": 0.99},
                {"word": "is", "start": 2.1, "end": 2.5, "probability": 0.99},
                {"word": "Clipwise.", "start": 2.6, "end": 3.8, "probability": 0.99},
            ],
        }
    ]
    sentences = extract_sentences(mock_segments)
    assert len(sentences) == 2
    assert sentences[0]["text"] == "Hello world!"
    assert sentences[1]["text"] == "This is Clipwise."


def test_generate_candidate_segments_enforces_duration():
    # Build a simulated 120-second transcript with sentences every 10 seconds
    mock_segments = []
    current_time = 0.0
    for i in range(12):
        sent_text = f"Sentence number {i} is here."
        words = [
            {"word": "Sentence", "start": current_time, "end": current_time + 1.5, "probability": 1.0},
            {"word": f"number", "start": current_time + 1.6, "end": current_time + 2.5, "probability": 1.0},
            {"word": f"{i}", "start": current_time + 2.6, "end": current_time + 3.5, "probability": 1.0},
            {"word": "is", "start": current_time + 3.6, "end": current_time + 4.5, "probability": 1.0},
            {"word": "here.", "start": current_time + 4.6, "end": current_time + 8.5, "probability": 1.0},
        ]
        mock_segments.append({
            "id": i,
            "start": current_time,
            "end": current_time + 8.5,
            "text": sent_text,
            "words": words,
        })
        current_time += 10.0

    mock_transcript = {"segments": mock_segments}
    candidates = generate_candidate_segments(mock_transcript, min_duration=15.0, max_duration=60.0)

    assert len(candidates) > 0
    for cand in candidates:
        assert 15.0 <= cand["duration"] <= 60.0
        assert cand["start"] < cand["end"]
        assert len(cand["text"]) > 0


def test_filter_overlapping_candidates():
    candidates = [
        {"start": 0.0, "end": 30.0, "duration": 30.0, "text": "Clip 1"},
        {"start": 2.0, "end": 32.0, "duration": 30.0, "text": "Clip 2 (almost identical)"},
        {"start": 60.0, "end": 90.0, "duration": 30.0, "text": "Clip 3"},
    ]
    filtered = filter_overlapping_candidates(candidates, max_iou=0.7)
    # The first two overlap heavily (>0.85 IoU), so only one should be kept
    assert len(filtered) == 2
    assert filtered[0]["start"] == 0.0
    assert filtered[1]["start"] == 60.0
