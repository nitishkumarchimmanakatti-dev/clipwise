"""User prompt guidance parser and candidate filter for Clipwise.

Allows users to specify:
1. Time range / boundaries: e.g. 'from 15:00 to 45:00', 'between 10m and 35m', 'first 20 mins', 'after 30:00'
2. Topic & theme focus: e.g. 'AI, humanoid robots, work ethic advice, success and failure'
"""

import re
from typing import Dict, Any, List, Optional, Tuple


def parse_time_token(token: str) -> Optional[float]:
    """Parse a time string like '15:00', '1:20:00', '15m', '900s' into seconds."""
    clean = token.strip().lower()

    # Format hh:mm:ss or mm:ss
    if ":" in clean:
        parts = clean.split(":")
        try:
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            elif len(parts) == 2:
                return int(parts[0]) * 60 + float(parts[1])
        except ValueError:
            return None

    # Format 15m, 15 min, 15 mins, 15 minutes
    m_match = re.match(r"^(\d+(?:\.\d+)?)\s*(?:m|min|mins|minute|minutes)$", clean)
    if m_match:
        return float(m_match.group(1)) * 60.0

    # Format 2h, 2 hr, 2 hours
    h_match = re.match(r"^(\d+(?:\.\d+)?)\s*(?:h|hr|hrs|hour|hours)$", clean)
    if h_match:
        return float(h_match.group(1)) * 3600.0

    # Format 900s
    s_match = re.match(r"^(\d+(?:\.\d+)?)\s*s(?:ec|ecs|econd|econds)?$", clean)
    if s_match:
        return float(s_match.group(1))

    return None


def parse_user_prompt(prompt: Optional[str]) -> Dict[str, Any]:
    """Parse time range constraints and topic keywords from a user guidance prompt."""
    if not prompt or not prompt.strip():
        return {
            "raw_prompt": "",
            "time_range": None,
            "topics": [],
            "has_filter": False,
        }

    raw = prompt.strip()
    working_text = raw.lower()

    time_range: Optional[Tuple[float, float]] = None

    # 1. Check patterns like 'first 20 mins' or 'first 15 minutes'
    first_match = re.search(r"\bfirst\s+(\d+(?:\.\d+)?)\s*(m|min|mins|minute|minutes|s|sec|secs|seconds)?\b", working_text)
    if first_match:
        dur = float(first_match.group(1))
        unit = (first_match.group(2) or "m").lower()
        if unit.startswith("s"):
            end_sec = dur
        elif unit.startswith("h"):
            end_sec = dur * 3600.0
        else:
            end_sec = dur * 60.0
        time_range = (0.0, end_sec)
        working_text = working_text.replace(first_match.group(0), " ")

    # 2. Check patterns like 'from X to Y', 'between X and Y', 'X - Y', 'X to Y'
    if not time_range:
        range_match = re.search(
            r"(?:from|between)?\s*(\d+:\d+(?::\d+)?|\d+\s*(?:m|min|mins|h|hr|hours|s))\s*(?:to|-|until|till|and)\s*(\d+:\d+(?::\d+)?|\d+\s*(?:m|min|mins|h|hr|hours|s))",
            working_text
        )
        if range_match:
            t1 = parse_time_token(range_match.group(1))
            t2 = parse_time_token(range_match.group(2))
            if t1 is not None and t2 is not None:
                start_sec = min(t1, t2)
                end_sec = max(t1, t2)
                time_range = (start_sec, end_sec)
                working_text = working_text.replace(range_match.group(0), " ")

    # 3. Check patterns like 'after X', 'from X onwards', 'starting at X'
    if not time_range:
        after_match = re.search(
            r"(?:after|starting at|starting from|from)\s*(\d+:\d+(?::\d+)?|\d+\s*(?:m|min|mins|h|hr|hours|s))(?:\s*onwards)?",
            working_text
        )
        if after_match:
            t = parse_time_token(after_match.group(1))
            if t is not None:
                time_range = (t, float("inf"))
                working_text = working_text.replace(after_match.group(0), " ")

    # Stop words to remove from topic extraction
    stop_words = {
        "from", "to", "between", "and", "in", "on", "at", "for", "of", "with",
        "the", "a", "an", "is", "are", "be", "should", "clips", "clip", "video",
        "videos", "generate", "extract", "focus", "related", "about", "things",
        "where", "after", "give", "me", "short", "long", "please", "make", "only"
    }

    # Extract topic terms
    tokens = re.findall(r"\b[a-zA-Z0-9_\-\$]+\b", working_text)
    topics = [t for t in tokens if len(t) > 2 and t not in stop_words]

    return {
        "raw_prompt": raw,
        "time_range": time_range,
        "topics": topics,
        "has_filter": bool(time_range or topics),
    }


def filter_and_boost_candidates_by_prompt(
    candidates: List[Dict[str, Any]],
    prompt: Optional[str],
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """Apply time range window filtering and semantic/keyword topic boosting to candidates."""
    if not candidates or not prompt or not prompt.strip():
        return candidates

    info = parse_user_prompt(prompt)
    if not info["has_filter"]:
        return candidates

    filtered = candidates
    time_range = info["time_range"]
    topics = info["topics"]

    # 1. Apply time window filter if specified
    if time_range:
        start_limit, end_limit = time_range
        # Select candidates that overlap with the user requested time window
        in_window = []
        for c in candidates:
            # Overlap check between [c["start"], c["end"]] and [start_limit, end_limit]
            inter = max(0.0, min(c["end"], end_limit) - max(c["start"], start_limit))
            if inter > 5.0 or (c["start"] >= start_limit and c["end"] <= end_limit):
                in_window.append(c)

        # If we have enough candidates inside the window, restrict strictly to the window
        if len(in_window) >= min(top_n, 3):
            filtered = in_window

    # 2. Score candidates on topic relevance
    if topics:
        for c in filtered:
            c_text_lower = c.get("text", "").lower()
            matched_keywords = []
            for t in topics:
                if t in c_text_lower:
                    matched_keywords.append(t)

            if matched_keywords:
                # Strong topic relevance bonus (+3.0 to +6.0)
                boost = min(len(matched_keywords) * 1.5, 4.5)
                c["hook_score"] = min(10.0, round(c.get("hook_score", 5.0) + boost, 1))
                tag = ", ".join(matched_keywords[:3])
                existing_why = c.get("why_this_clip", "")
                c["why_this_clip"] = f"[Focus: {tag}] {existing_why}"

    return filtered
