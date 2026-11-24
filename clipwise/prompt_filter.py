"""User prompt guidance parser and candidate filter for Clipwise.

Allows users to specify:
1. Time range / boundaries:
   - 'from 5 to 10 minutes', '5 to 10 mins', 'between 10m and 35m', '5 - 10 minutes'
   - 'from 15:00 to 45:00', '15.00 to 45.00', '10:00 - 20:00'
   - 'first 20 mins', 'after 30:00', 'starting at 15m'
2. Topic & theme focus:
   - 'AI, humanoid robots, work ethic advice, success and failure'
"""

import re
from typing import Dict, Any, List, Optional, Tuple


def parse_time_token(val_str: Optional[str], unit_hint: Optional[str] = None) -> Optional[float]:
    """Parse a time token like '15:00', '1:20:00', '15.30', '15m', '900s', '15' into seconds."""
    if not val_str:
        return None
    clean = val_str.strip().lower()

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

    # Format dot notation for time like 5.30 (5 min 30 sec) or 10.00 (10 min)
    if re.match(r"^\d+\.\d{1,2}$", clean):
        parts = clean.split(".")
        try:
            m = int(parts[0])
            s = int(parts[1]) if len(parts[1]) == 2 else int(parts[1]) * 10
            return m * 60.0 + s
        except ValueError:
            pass

    # Format 15m, 15 min, 15 mins, 15 minutes
    m_match = re.match(r"^(\d+(?:\.\d+)?)\s*(?:m|min|mins|minute|minutes)$", clean)
    if m_match:
        return float(m_match.group(1)) * 60.0

    # Format 2h, 2 hr, 2 hours
    h_match = re.match(r"^(\d+(?:\.\d+)?)\s*(?:h|hr|hrs|hour|hours)$", clean)
    if h_match:
        return float(h_match.group(1)) * 3600.0

    # Format 900s
    s_match = re.match(r"^(\d+(?:\.\d+)?)\s*(?:s|sec|secs|second|seconds)$", clean)
    if s_match:
        return float(s_match.group(1))

    # Raw number with optional unit hint
    num_match = re.match(r"^(\d+(?:\.\d+)?)$", clean)
    if num_match:
        val = float(num_match.group(1))
        unit = (unit_hint or "m").lower()
        if unit.startswith("s"):
            return val
        elif unit.startswith("h"):
            return val * 3600.0
        else:
            # In video clipping context, raw numbers like 5, 10, 25 mean minutes
            return val * 60.0

    return None


def extract_time_range_from_text(text: str) -> Optional[Tuple[float, float]]:
    """Robustly extract start and end timestamps from freeform natural language text."""
    text_lower = text.lower()

    # 1. 'first X mins/minutes'
    first_m = re.search(r"\bfirst\s+(\d+(?:\.\d+)?)\s*(m|min|mins|minute|minutes|s|sec|secs|seconds)?\b", text_lower)
    if first_m:
        dur = float(first_m.group(1))
        unit = (first_m.group(2) or "m").lower()
        end_s = dur if unit.startswith("s") else dur * 60.0
        return (0.0, end_s)

    # 2. 'from X to Y [unit]', 'between X and Y [unit]', 'X - Y [unit]', 'X to Y [unit]'
    range_regex = r"(?:from|between|around|timeline:?)?\s*(\d+[:.]\d+|\d+(?:\.\d+)?(?:\s*[a-z]+)?)\s*(?:to|-|until|till|and)\s*(\d+[:.]\d+|\d+(?:\.\d+)?(?:\s*[a-z]+)?)\s*(mins?|minutes?|m|seconds?|secs?|s|hours?|hrs?|h)?"
    for m in re.finditer(range_regex, text_lower):
        part1 = m.group(1).strip()
        part2 = m.group(2).strip()
        unit = m.group(3)
        t1 = parse_time_token(part1, unit)
        t2 = parse_time_token(part2, unit)
        if t1 is not None and t2 is not None and t1 != t2:
            return (min(t1, t2), max(t1, t2))

    # 3. 'after X', 'from X onwards', 'starting at X'
    after_m = re.search(r"(?:after|starting at|starting from|from)\s*(\d+[:.]\d+|\d+(?:\.\d+)?(?:\s*[a-z]+)?)(?:\s*onwards)?", text_lower)
    if after_m:
        t = parse_time_token(after_m.group(1))
        if t is not None:
            return (t, float("inf"))

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

    time_range = extract_time_range_from_text(working_text)

    # Stop words to remove from topic extraction
    stop_words = {
        "from", "to", "between", "and", "in", "on", "at", "for", "of", "with",
        "the", "a", "an", "is", "are", "be", "should", "clips", "clip", "video",
        "videos", "generate", "extract", "focus", "related", "about", "things",
        "where", "after", "give", "me", "short", "long", "please", "make", "only",
        "timeline", "time", "start", "end", "minutes", "minute", "mins", "min", "seconds", "sec"
    }

    tokens = re.findall(r"\b[a-zA-Z0-9_\-\$]+\b", working_text)
    topics = [t for t in tokens if len(t) > 2 and t not in stop_words and not t.isdigit()]

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
    """Strictly enforce time range filtering and boost prompt topic relevance."""
    if not candidates or not prompt or not prompt.strip():
        return candidates

    info = parse_user_prompt(prompt)
    if not info["has_filter"]:
        return candidates

    filtered = candidates
    time_range = info["time_range"]
    topics = info["topics"]

    # 1. Strictly enforce user-specified time range
    if time_range:
        start_limit, end_limit = time_range
        in_window = []
        for c in candidates:
            # Overlap check between candidate and requested timeline window
            inter = max(0.0, min(c["end"], end_limit) - max(c["start"], start_limit))
            # Include if candidate overlaps with requested window
            if inter > 0.0 or (c["start"] >= start_limit and c["end"] <= end_limit):
                in_window.append(c)

        if in_window:
            filtered = in_window
        else:
            # If no candidate fell strictly inside the window, pick candidates closest to the window center
            target_mid = (start_limit + (end_limit if end_limit != float("inf") else start_limit + 300)) / 2.0
            sorted_by_proximity = sorted(candidates, key=lambda c: abs(((c["start"] + c["end"]) / 2.0) - target_mid))
            filtered = sorted_by_proximity[:max(top_n, 5)]

    # 2. Score candidates on topic relevance
    if topics:
        for c in filtered:
            c_text_lower = c.get("text", "").lower()
            matched_keywords = [t for t in topics if t in c_text_lower]

            if matched_keywords:
                boost = min(len(matched_keywords) * 1.5, 4.5)
                c["hook_score"] = min(10.0, round(c.get("hook_score", 5.0) + boost, 1))
                tag = ", ".join(matched_keywords[:3])
                existing_why = c.get("why_this_clip", "")
                c["why_this_clip"] = f"[Focus: {tag}] {existing_why}"

    return filtered
