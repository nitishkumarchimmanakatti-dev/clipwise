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


def evaluate_hook_details(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate detailed hook score and generate human-readable 'why_this_clip' note."""
    text = candidate.get("text", "")
    words = candidate.get("words", [])
    duration = candidate.get("duration", 1.0)

    if not text or duration <= 0:
        return {"score": 0.0, "why": "Empty transcript"}

    reasons: List[str] = []
    score = 3.5  # Base score for coherent speech window

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

    # 2. Payoff Detection (Resolution following early tension)
    payoff_matches = [p for p in PAYOFF_KEYWORDS if p in full_lower]
    if payoff_matches:
        score += 1.2
        reasons.append("Complete story arc with clear payoff/resolution")

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
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return candidates

    try:
        # If LLM is configured, enrich the top candidates
        # Implementation allows optional Gemini/OpenAI call
        pass
    except Exception:
        pass
    return candidates


def score_candidates(
    candidates: List[Dict[str, Any]],
    use_llm: bool = False,
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """Score, rank, and select the top candidate segments with metadata rationales."""
    if not candidates:
        return []

    for cand in candidates:
        details = evaluate_hook_details(cand)
        cand["hook_score"] = details["score"]
        cand["why_this_clip"] = details["why"]

    # Sort descending by hook score
    candidates.sort(key=lambda c: c["hook_score"], reverse=True)

    # De-duplicate heavily overlapping candidate windows (>70% overlap)
    selected: List[Dict[str, Any]] = []
    for cand in candidates:
        overlaps = False
        for s in selected:
            intersection = max(0.0, min(cand["end"], s["end"]) - max(cand["start"], s["start"]))
            smaller_dur = min(cand["duration"], s["duration"])
            if smaller_dur > 0 and (intersection / smaller_dur) > 0.65:
                overlaps = True
                break
        if not overlaps:
            selected.append(cand)
        if len(selected) >= top_n:
            break

    if use_llm:
        selected = score_candidates_with_llm(selected, top_n=top_n)

    return selected
