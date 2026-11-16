"""Hook scoring engine: rule-based signals and optional LLM ranking."""

import re
import os
import json
from typing import List, Dict, Any, Optional

# High-impact hook keywords frequently found in top-performing YouTube Shorts
HOOK_KEYWORDS = {
    "secret", "secrets", "never", "always", "mistake", "mistakes", "truth",
    "how to", "why you", "stop", "proven", "crazy", "warning", "trick",
    "revealed", "insane", "hack", "hacks", "nobody", "everyone", "shocking",
    "watch this", "don't", "avoid", "lesson", "rule", "hidden", "best way",
    "worst", "ultimate", "guaranteed", "easiest", "fastest", "billion", "million"
}


def calculate_rule_based_hook_score(candidate: Dict[str, Any]) -> float:
    """Calculate engagement hook score (0.0 to 10.0) based on linguistic & speech signals."""
    text = candidate.get("text", "")
    words = candidate.get("words", [])
    duration = candidate.get("duration", 1.0)

    if not text or duration <= 0:
        return 0.0

    score = 3.0  # Base score for any coherent sentence

    # 1. Analyze the Hook (First 5 seconds or first 15 words)
    hook_words = [w["word"] for w in words if (w["start"] - candidate["start"]) <= 5.0]
    hook_text = " ".join(hook_words) if hook_words else " ".join([w["word"] for w in words[:15]])
    hook_lower = hook_text.lower()
    full_lower = text.lower()

    # Question Hook (Curiosity gap)
    if "?" in hook_text:
        score += 2.0
    elif "?" in text:
        score += 1.0

    # Exclamation (Energy/Urgency)
    if "!" in hook_text:
        score += 1.5
    elif "!" in text:
        score += 0.8

    # Numbers and Statistics (e.g., "$10,000", "5 reasons", "10x")
    number_pattern = r"\b\d+([,.]\d+)?(%|k|m|b)?\b"
    if re.search(number_pattern, hook_text, re.IGNORECASE):
        score += 1.8
    elif re.search(number_pattern, text, re.IGNORECASE):
        score += 1.0

    # Strong Keyword Matches
    hook_kw_hits = sum(1 for kw in HOOK_KEYWORDS if kw in hook_lower)
    score += min(hook_kw_hits * 1.0, 2.5)

    full_kw_hits = sum(1 for kw in HOOK_KEYWORDS if kw in full_lower)
    score += min(full_kw_hits * 0.3, 1.5)

    # Speech Pace (Words Per Minute)
    # Ideal energetic short-form speech is 135 - 180 wpm
    word_count = len(words) if words else len(text.split())
    wpm = (word_count / duration) * 60.0

    if 135 <= wpm <= 185:
        score += 1.2  # optimal energetic pace
    elif 110 <= wpm < 135 or 185 < wpm <= 210:
        score += 0.5  # acceptable
    elif wpm < 90:
        score -= 1.0  # too sluggish for a hook
    elif wpm > 240:
        score -= 0.5  # unintelligibly fast

    # Starting Silence Penalty
    # If the speaker waits > 0.8s before speaking, viewers swipe away
    if words and len(words) > 0:
        initial_silence = words[0]["start"] - candidate["start"]
        if initial_silence <= 0.3:
            score += 0.8  # Instant speech hook
        elif initial_silence > 1.2:
            score -= 1.0

    # Normalize to 0.0 - 10.0 range
    final_score = max(0.0, min(10.0, round(score, 1)))
    return final_score


def score_candidates(
    candidates: List[Dict[str, Any]],
    use_llm: bool = False,
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """Score all candidates using rule-based signals and optionally refine with LLM."""
    if not candidates:
        return []

    # Apply rule-based hook scores
    for cand in candidates:
        cand["hook_score"] = calculate_rule_based_hook_score(cand)
        cand["score_breakdown"] = "rule_based"

    # Sort descending by hook score
    candidates.sort(key=lambda c: c["hook_score"], reverse=True)

    # Optional LLM refinement for top candidates
    if use_llm:
        candidates = refine_scores_with_llm(candidates, top_k=min(20, len(candidates)))
        candidates.sort(key=lambda c: c["hook_score"], reverse=True)

    return candidates[:top_n]


def refine_scores_with_llm(candidates: List[Dict[str, Any]], top_k: int = 20) -> List[Dict[str, Any]]:
    """Optional LLM scoring interface.
    
    Reads API key from environment (GEMINI_API_KEY or OPENAI_API_KEY).
    If no key or client is available, gracefully retains rule-based scores.
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if not gemini_key and not openai_key:
        return candidates  # Fallback gracefully to rule-based scores

    subset = candidates[:top_k]

    prompt_data = [
        {
            "id": idx,
            "duration": c["duration"],
            "text": c["text"]
        }
        for idx, c in enumerate(subset)
    ]

    prompt = (
        "You are an expert viral YouTube Shorts producer. "
        "Score each video clip candidate for its 'hook strength' and viral retention potential on a scale of 0.0 to 10.0. "
        "Respond ONLY with a JSON list of objects: [{\"id\": int, \"score\": float, \"reason\": string}].\n\n"
        f"Candidates:\n{json.dumps(prompt_data, indent=2)}"
    )

    try:
        # LLM Call wrapper
        llm_response = call_llm_provider(prompt, gemini_key=gemini_key, openai_key=openai_key)
        if llm_response:
            score_map = {item["id"]: item for item in llm_response if "id" in item and "score" in item}
            for idx, c in enumerate(subset):
                if idx in score_map:
                    # Blend 60% LLM + 40% rule-based
                    llm_val = float(score_map[idx]["score"])
                    blended = round(0.6 * llm_val + 0.4 * c["hook_score"], 1)
                    c["hook_score"] = max(0.0, min(10.0, blended))
                    c["hook_reason"] = score_map[idx].get("reason", "")
                    c["score_breakdown"] = "llm_blended"
    except Exception:
        # LLM scoring failed or returned non-JSON; keep rule-based scores
        pass

    return candidates


def call_llm_provider(prompt: str, gemini_key: Optional[str] = None, openai_key: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
    """Single swap-friendly LLM provider caller."""
    # Priority 1: Gemini if key available
    if gemini_key:
        try:
            import urllib.request
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"}
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text_content = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text_content)
        except Exception:
            pass

    # Priority 2: OpenAI if key available
    if openai_key:
        try:
            import urllib.request
            url = "https://api.openai.com/v1/chat/completions"
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are a JSON-only response engine."},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"}
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {openai_key}"
                }
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text_content = data["choices"][0]["message"]["content"]
                parsed = json.loads(text_content)
                if isinstance(parsed, list):
                    return parsed
                if isinstance(parsed, dict) and "candidates" in parsed:
                    return parsed["candidates"]
        except Exception:
            pass

    return None
