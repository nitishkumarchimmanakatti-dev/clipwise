"""Tests for prompt guidance parsing, time-range window filtering, and topic boosting."""

import pytest
from clipwise.prompt_filter import parse_user_prompt, filter_and_boost_candidates_by_prompt
from clipwise.score import score_candidates


def test_parse_user_prompt_time_ranges():
    # Test 'from 15:00 to 45:00'
    p1 = parse_user_prompt("From 15:00 to 45:00 focus on Tesla Optimus")
    assert p1["has_filter"] is True
    assert p1["time_range"] == (900.0, 2700.0)
    assert "optimus" in p1["topics"] or "tesla" in p1["topics"]

    # Test 'between 10m and 35m'
    p2 = parse_user_prompt("between 10m and 35m AI and robotics")
    assert p2["time_range"] == (600.0, 2100.0)
    assert "robotics" in p2["topics"]

    # Test 'first 20 mins'
    p3 = parse_user_prompt("first 20 mins of podcast")
    assert p3["time_range"] == (0.0, 1200.0)

    # Test pure topic prompt without time
    p4 = parse_user_prompt("Elon Musk work ethic and hardcore advice")
    assert p4["time_range"] is None
    assert "ethic" in p4["topics"]
    assert "hardcore" in p4["topics"]


def test_filter_and_boost_candidates_by_prompt():
    candidates = [
        {"start": 100.0, "end": 130.0, "duration": 30.0, "text": "Talking about weather and breakfast.", "hook_score": 7.0},
        {"start": 1000.0, "end": 1030.0, "duration": 30.0, "text": "Optimus humanoid robot will revolutionize the factory floor.", "hook_score": 7.0},
        {"start": 1200.0, "end": 1230.0, "duration": 30.0, "text": "Tesla AI neural nets are learning physics directly.", "hook_score": 7.0},
        {"start": 2500.0, "end": 2530.0, "duration": 30.0, "text": "Random discussion about movies.", "hook_score": 7.0},
    ]

    prompt = "From 15:00 to 25:00 focus on Optimus robot and AI neural nets"
    boosted = filter_and_boost_candidates_by_prompt(candidates, prompt, top_n=2)

    # Weather (100s) and Movies (2500s) are outside 15:00 - 25:00 (900s - 1500s)
    # The two inside candidates should be selected and boosted
    times = [c["start"] for c in boosted]
    assert 1000.0 in times
    assert 1200.0 in times
    # Target topic keywords should give boost
    assert boosted[0]["hook_score"] > 7.0


def test_score_candidates_with_prompt_guidance():
    candidates = [
        {"start": 50.0, "end": 80.0, "duration": 30.0, "text": "Standard introduction.", "words": []},
        {"start": 950.0, "end": 980.0, "duration": 30.0, "text": "Why Optimus robot is our biggest invention yet?", "words": []},
        {"start": 1100.0, "end": 1130.0, "duration": 30.0, "text": "Secret of hard work and relentless discipline.", "words": []},
        {"start": 2800.0, "end": 2830.0, "duration": 30.0, "text": "Final concluding remarks.", "words": []},
    ]

    prompt = "From 15:00 to 25:00 focus on Optimus robot"
    selected = score_candidates(candidates, top_n=2, prompt=prompt)

    assert len(selected) >= 1
    # Candidate about Optimus should be chosen and boosted
    optimus_clip = [c for c in selected if "Optimus" in c["text"]]
    assert len(optimus_clip) == 1
    assert "Focus" in optimus_clip[0].get("why_this_clip", "")
