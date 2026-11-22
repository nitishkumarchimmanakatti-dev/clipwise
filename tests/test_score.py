"""Tests for hook scoring signals and ranking."""

from clipwise.score import calculate_rule_based_hook_score, score_candidates, evaluate_hook_details


def test_question_hook_scores_higher_than_plain_statement():
    q_cand = {
        "start": 0.0,
        "end": 20.0,
        "duration": 20.0,
        "text": "Did you know that 99% of programmers make this fatal mistake?",
        "words": [
            {"word": "Did", "start": 0.1, "end": 0.4},
            {"word": "you", "start": 0.5, "end": 0.8},
            {"word": "know", "start": 0.9, "end": 1.2},
            {"word": "that", "start": 1.3, "end": 1.5},
            {"word": "99%", "start": 1.6, "end": 2.2},
            {"word": "of", "start": 2.3, "end": 2.5},
            {"word": "programmers", "start": 2.6, "end": 3.2},
            {"word": "make", "start": 3.3, "end": 3.6},
            {"word": "this", "start": 3.7, "end": 4.0},
            {"word": "fatal", "start": 4.1, "end": 4.5},
            {"word": "mistake?", "start": 4.6, "end": 5.2},
        ],
    }

    plain_cand = {
        "start": 0.0,
        "end": 20.0,
        "duration": 20.0,
        "text": "We are walking along the sidewalk on a normal cloudy day.",
        "words": [
            {"word": "We", "start": 1.5, "end": 2.0},
            {"word": "are", "start": 2.1, "end": 2.4},
            {"word": "walking", "start": 2.5, "end": 3.0},
            {"word": "along", "start": 3.1, "end": 3.5},
            {"word": "the", "start": 3.6, "end": 3.8},
            {"word": "sidewalk.", "start": 3.9, "end": 4.5},
        ],
    }

    q_score = calculate_rule_based_hook_score(q_cand)
    plain_score = calculate_rule_based_hook_score(plain_cand)

    assert q_score > plain_score
    assert q_score >= 7.0  # Questions + 99% + 'mistake' keyword gives strong hook


def test_score_candidates_ranking():
    candidates = [
        {"start": 0.0, "end": 25.0, "duration": 25.0, "text": "Ordinary conversation with no hooks.", "words": []},
        {"start": 30.0, "end": 55.0, "duration": 25.0, "text": "Stop doing this crazy mistake right now!", "words": []},
    ]

    scored = score_candidates(candidates, top_n=2)
    assert len(scored) == 2
    # Should be sorted chronologically for consistent sequence narrative
    assert scored[0]["start"] < scored[1]["start"]
    assert scored[0]["part_number"] == 1
    assert scored[1]["part_number"] == 2
    assert scored[0]["total_parts"] == 2
    assert scored[1]["total_parts"] == 2
    assert "why_this_clip" in scored[0]


def test_score_candidates_strict_no_overlap():
    # Two candidates that overlap temporally: one should be eliminated so there are ZERO duplicate seconds
    candidates = [
        {"start": 10.0, "end": 35.0, "duration": 25.0, "text": "Did you know 90% of millionaires invest early?", "words": []},
        {"start": 20.0, "end": 45.0, "duration": 25.0, "text": "Invest early and avoid this trap.", "words": []},
        {"start": 60.0, "end": 85.0, "duration": 25.0, "text": "Here is rule number three of wealth creation.", "words": []},
    ]

    scored = score_candidates(candidates, top_n=3)
    # The overlapping candidate (20-45s) must be discarded, leaving only disjoint segments
    assert len(scored) == 2
    assert scored[0]["start"] == 10.0
    assert scored[0]["end"] == 35.0
    assert scored[1]["start"] == 60.0
    assert scored[1]["end"] == 85.0
    assert scored[0]["part_number"] == 1
    assert scored[1]["part_number"] == 2


def test_hindi_hinglish_hook_scoring():
    hi_cand = {
        "start": 0.0,
        "end": 30.0,
        "duration": 30.0,
        "text": "Yeh sabse bada raaz hai jo kisi ne nahi bataya!",
        "words": [
            {"word": "Yeh", "start": 0.1, "end": 0.4},
            {"word": "sabse", "start": 0.5, "end": 0.8},
            {"word": "bada", "start": 0.9, "end": 1.2},
            {"word": "raaz", "start": 1.3, "end": 1.8},
            {"word": "hai!", "start": 1.9, "end": 2.3},
        ],
    }
    score_details = evaluate_hook_details(hi_cand)
    assert score_details["score"] >= 6.5
    assert "raaz" in score_details["why"].lower() or "hook" in score_details["why"].lower()


def test_metadata_sequential_parts():
    from clipwise.metadata import create_clip_metadata

    cand = {
        "start": 10.0,
        "end": 35.0,
        "duration": 25.0,
        "text": "Why do most people fail in their first business venture?",
        "hook_score": 8.5,
        "part_number": 1,
        "total_parts": 3,
    }
    src_meta = {
        "title": "Mastering Entrepreneurship Podcast",
        "channel": "Tech Leaders",
        "webpage_url": "https://youtube.com/watch?v=sample123",
    }

    meta = create_clip_metadata(cand, src_meta, "sample_clip_01")
    assert meta["part_number"] == 1
    assert meta["total_parts"] == 3
    assert "Part 1 |" in meta["title"]
    assert "Part 1 of 3" in meta["description"]
    assert "Watch Part 2 next" in meta["description"]
