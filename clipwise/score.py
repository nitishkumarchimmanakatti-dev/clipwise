"""Hook scoring engine for YouTube Shorts: rule-based signals and optional LLM ranking."""

import re
import os
import json
from typing import List, Dict, Any, Optional

# High-impact hook keywords in English and Hindi/Hinglish
HOOK_KEYWORDS_EN = {
    "secret", "secrets", "never", "always", "mistake", "mistakes", "truth",
    "how to", "why you", "stop doing", "stop", "proven", "crazy", "warning", "trick",
    "revealed", "insane", "hack", "hacks", "nobody tells you", "nobody", "everyone", "shocking",
    "watch this", "don't", "avoid", "lesson", "rule", "hidden", "best way",
    "worst", "ultimate", "guaranteed", "easiest", "fastest", "billion", "million"
}

HOOK_KEYWORDS_HI = {
    "raaz", "galti", "sach", "kyun", "kaise", "hamesha", "kabhi nahi", "kabhi mat",
    "sabse bada", "sabse badi", "mat karna", "asliyat", "dekho", "khatarnaak", "jaan lo",
    "dhyan se", "pachtana", "zaroori", "aisa kyun"
}

# Payoff and resolution signals
PAYOFF_KEYWORDS = {
    "because", "isliye", "result", "finally", "tabhi", "that's why", "answer",
    "the reason", "solution", "here is why", "yeh raha", "samjhe", "conclusion"
}

# Strong story conclusion, moral, and takeaway indicators
STORY_CONCLUSION_KEYWORDS = {
    "finally", "in the end", "the result", "remember", "never forget",
    "that is why", "that's why", "bottom line", "the truth is",
    "now you know", "takeaway", "lesson", "subscribe", "follow for more",
    "try this", "save this", "share this", "what do you think", "key is",
    "moral", "solution", "conclusion", "answer", "proved", "outcome",
    "aakhri mein", "ant mein", "asli baat", "yeh seekh", "yaad rakhna",
    "isliye", "tab jakar", "to yeh tha", "hamesha yaad", "samjhe",
    "fayda", "nateeja", "seekh lo"
}


def evaluate_hook_details(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate detailed hook score and generate human-readable 'why_this_clip' note."""
    text = candidate.get("text", "")
    words = candidate.get("words", [])
    duration = candidate.get("duration", 1.0)

    if not text or duration <= 0:
        return {"score": 0.0, "why": "Empty transcript"}

    reasons: List[str] = []
    score = 4.0  # Base score for coherent speech window

    # 1. Analyze the Hook (first 5.5 seconds or first 15 words)
    hook_words = [w["word"] for w in words if (w["start"] - candidate["start"]) <= 5.5]
    if hook_words:
        hook_text = " ".join(hook_words)
    elif words:
        hook_text = " ".join([w["word"] for w in words[:15]])
    else:
        hook_text = " ".join(text.split()[:15])

    hook_lower = hook_text.lower()
    full_lower = text.lower()

    # Question Hook (Curiosity gap)
    if "?" in hook_text:
        score += 2.2
        reasons.append("Opens with an engaging curiosity question")
    elif "?" in text:
        score += 1.0

    # Exclamation (Urgency/Energy)
    if "!" in hook_text:
        score += 1.5
        reasons.append("Energetic and punchy opening exclamation")

    # Numbers and Statistics (e.g. "3 mistakes", "10x", "$50,000")
    num_match = re.search(r"\b\d+([,.]\d+)?(%|k|m|b)?\b", hook_text, re.IGNORECASE)
    if num_match:
        score += 1.8
        reasons.append(f"Contains concrete numbers/results ({num_match.group(0)})")

    # Hook Keyword Matches (English + Hindi)
    en_matches = [kw for kw in HOOK_KEYWORDS_EN if kw in hook_lower]
    hi_matches = [kw for kw in HOOK_KEYWORDS_HI if kw in hook_lower]
    all_hook_kw = en_matches + hi_matches
    if all_hook_kw:
        score += min(len(all_hook_kw) * 1.2, 2.8)
        reasons.append(f"High-retention hook keywords: {', '.join(all_hook_kw[:3])}")

    # 2. Story Arc & Narrative Completeness Evaluation
    ending_sent = candidate.get("ending_sentence", "")
    if not ending_sent:
        sents = re.split(r"(?<=[.!?])\s+", text.strip())
        ending_sent = sents[-1] if sents else text
    ending_lower = ending_sent.lower()

    payoff_matches = [p for p in PAYOFF_KEYWORDS if p in full_lower]
    has_conclusion_marker = any(ck in ending_lower for ck in STORY_CONCLUSION_KEYWORDS)
    if has_conclusion_marker or payoff_matches:
        score += 1.8
        reasons.append("Complete story resolution with satisfying payoff/takeaway")

    # Multi-beat narrative development (Hook -> Story -> Resolution)
    sentence_count = candidate.get("sentence_count", len(re.split(r"(?<=[.!?])\s+", text.strip())))
    if sentence_count >= 3:
        score += 1.0
        reasons.append(f"Multi-beat narrative structure ({sentence_count} sentences)")

    # Penalize cliffhanger endings (ending on an open question without answer when duration > 25s)
    if ending_sent.strip().endswith("?") and duration > 25.0:
        if not any(cta in ending_lower for cta in ["what do you think", "did you know", "kaisa laga", "right?"]):
            score -= 2.0
            reasons.append("Cliffhanger ending without resolved answer")

    # 3. Speech Pace Dynamics (Words per Minute)
    word_count = len(words) if words else len(text.split())
    wpm = (word_count / duration) * 60.0
    if 135 <= wpm <= 185:
        score += 1.0  # optimal energetic pace
    elif wpm < 100:
        score -= 1.0
        reasons.append("Sluggish pace")
    elif wpm > 240:
        score -= 0.8
        reasons.append("Very fast speech rate")

    # 4. Silence Penalties
    # Check start silence
    if words:
        start_delay = words[0]["start"] - candidate["start"]
        if start_delay <= 0.3:
            score += 0.6  # Instant speech on frame 1
        elif start_delay > 1.2:
            score -= 1.2

    # Check internal gaps (>1.5s silence)
    has_dead_air = False
    for i in range(len(words) - 1):
        if words[i + 1]["start"] - words[i]["end"] > 1.5:
            has_dead_air = True
            break
    if has_dead_air:
        score -= 1.5
        reasons.append("Contains long pause/dead air")

    # Check context dependency
    if candidate.get("has_dependency"):
        score -= 2.0
        reasons.append("Relies on earlier video context")

    # Target length bonus (25s - 45s performs best on YouTube Shorts)
    if 25.0 <= duration <= 45.0:
        score += 0.8
        reasons.append("Sweet-spot Shorts duration (25-45s)")

    final_score = max(1.0, min(10.0, round(score, 1)))
    summary_why = "; ".join(reasons) if reasons else "Coherent standalone thought"

    return {
        "score": final_score,
        "why": summary_why,
    }


def calculate_rule_based_hook_score(candidate: Dict[str, Any]) -> float:
    """Calculate engagement hook score (0.0 to 10.0)."""
    res = evaluate_hook_details(candidate)
    return res["score"]


def score_candidates_with_llm(
    candidates: List[Dict[str, Any]],
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """Optional LLM enrichment for hook scoring and viral rationale (Gemini / OpenAI)."""
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if not (gemini_key or openai_key) or not candidates:
        return candidates

    try:
        import urllib.request
        excerpts = []
        for i, c in enumerate(candidates[:top_n]):
            excerpts.append({
                "index": i,
                "text": c.get("text", "")[:300],
                "duration": round(c.get("duration", 0), 1),
                "rule_score": c.get("hook_score", 5.0),
            })

        prompt = (
            "You are an expert viral YouTube Shorts editor. Rate the following clip excerpts "
            "from 1.0 to 10.0 based on: 1) Hook strength in first 3 seconds, 2) Standalone clarity, "
            "and 3) Payoff satisfaction. Return a JSON object formatted as: "
            '{"ratings": [{"index": 0, "score": 8.5, "why": "Captivating question hook with clear takeaway"}]}.\n\n'
            f"Excerpts:\n{json.dumps(excerpts)}"
        )

        if gemini_key:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
            req_data = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"response_mime_type": "application/json"}
            }).encode("utf-8")
            req = urllib.request.Request(url, data=req_data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                text_resp = result["candidates"][0]["content"]["parts"][0]["text"]
                data = json.loads(text_resp)
                ratings = {item["index"]: item for item in data.get("ratings", [])}
                for i, c in enumerate(candidates[:top_n]):
                    if i in ratings:
                        c["hook_score"] = float(ratings[i].get("score", c.get("hook_score", 5.0)))
                        c["why_this_clip"] = f"[AI] {ratings[i].get('why', c.get('why_this_clip', ''))}"
                candidates.sort(key=lambda x: x.get("hook_score", 0), reverse=True)
    except Exception:
        # Gracefully preserve rule-based scoring on any network or API issue
        pass

    return candidates


def score_candidates(
    candidates: List[Dict[str, Any]],
    use_llm: bool = False,
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """Score, rank, and select candidate segments distributed across the entire video timeline.

    Guarantees:
    1. Full Timeline Coverage: Extracts the best clips from the starting hook all the way to the final climax/ending.
    2. Strict Zero Overlap: Every clip is completely unique with 0.0s overlap.
    3. Chronological Narrative Sequence: Clips are arranged sequentially (Part 1 to Part N).
    """
    if not candidates:
        return []

    for cand in candidates:
        details = evaluate_hook_details(cand)
        cand["hook_score"] = details["score"]
        cand["why_this_clip"] = details["why"]

    # If only 1 clip requested or 1 candidate available, pick the highest hook score
    if top_n <= 1 or len(candidates) <= 1:
        best = max(candidates, key=lambda c: c["hook_score"])
        best["part_number"] = 1
        best["total_parts"] = 1
        return [best]

    # Timeline span across candidates
    t_min = min(c["start"] for c in candidates)
    t_max = max(c["end"] for c in candidates)
    timeline_span = t_max - t_min

    # Sort candidates descending by hook score
    candidates_by_score = sorted(candidates, key=lambda c: c["hook_score"], reverse=True)

    selected: List[Dict[str, Any]] = []

    def is_overlapping(cand: Dict[str, Any], current_list: List[Dict[str, Any]]) -> bool:
        for s in current_list:
            inter = max(0.0, min(cand["end"], s["end"]) - max(cand["start"], s["start"]))
            if inter > 0.0:
                return True
        return False

    if timeline_span > 0:
        # Divide video timeline into top_n chronological buckets
        # Bucket 0: Start of video (opening hook)
        # Buckets 1..N-2: Middle progressive story arcs
        # Bucket N-1: Climax, ending conclusion, and final takeaway
        bucket_size = timeline_span / top_n
        buckets: List[List[Dict[str, Any]]] = [[] for _ in range(top_n)]

        for cand in candidates_by_score:
            mid = (cand["start"] + cand["end"]) / 2.0
            b_idx = int((mid - t_min) / bucket_size)
            b_idx = min(max(b_idx, 0), top_n - 1)
            buckets[b_idx].append(cand)

        # Primary Pass: Select the best non-overlapping candidate from each bucket (0 to top_n - 1)
        # This guarantees representation from the start, progressive middle chapters, and final climax
        for b_idx in range(top_n):
            for cand in buckets[b_idx]:
                if not is_overlapping(cand, selected):
                    selected.append(cand)
                    break

    # Secondary Pass: If any bucket was empty or conflicted, fill remaining slots
    # with the highest-scoring non-overlapping candidates across the video
    if len(selected) < top_n:
        for cand in candidates_by_score:
            if cand not in selected and not is_overlapping(cand, selected):
                selected.append(cand)
                if len(selected) >= top_n:
                    break

    if use_llm:
        selected = score_candidates_with_llm(selected, top_n=top_n)

    # Sort selected candidates chronologically so clips form a coherent sequential series from start to climax
    selected.sort(key=lambda c: c["start"])

    # Number the parts sequentially
    total_parts = len(selected)
    for idx, cand in enumerate(selected, start=1):
        cand["part_number"] = idx
        cand["total_parts"] = total_parts

    return selected
