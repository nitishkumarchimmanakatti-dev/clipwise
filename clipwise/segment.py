"""Hook-first candidate segmentation engine for YouTube Shorts (15-60s)."""

from typing import List, Dict, Any
import re
from clipwise.config import MIN_CLIP_DURATION, MAX_CLIP_DURATION, TARGET_CLIP_DURATION

# Disallowed filler words and opening patterns that weaken a Short's hook
FILLER_OPENERS = [
    "so basically", "basically", "hello guys", "hey guys", "hi guys", "what's up guys",
    "um", "uh", "you know", "actually", "alright guys", "ok so", "okay so",
    "toh basically", "haan toh", "namaste dosto", "hello dosto", "aur bhai",
]

# Mid-thought conjunctions that signal the clip starts without context
MID_THOUGHT_STARTERS = ["and", "but", "or", "so", "because", "lekin", "aur", "magar", "par"]

# Dependent context indicators that imply earlier video knowledge
DEPENDENT_PHRASES = [
    "as i said before", "like i mentioned", "as we saw earlier", "as i told you",
    "in the last part", "jaise maine pehle kaha", "pichli video mein", "jaise pehle bataya"
]

# Continuation words that signal an unfinished, dangling clause if placed at clip end
UNRESOLVED_ENDINGS = {
    "and", "or", "but", "so", "because", "like", "which", "that", "that's",
    "to", "in", "of", "with", "if", "when", "while", "where", "since",
    "although", "though", "even", "then", "also", "for", "as", "about",
    "ki", "aur", "ya", "lekin", "magar", "par", "isliye", "kyun", "jaise",
    "matlab", "agar", "jab", "tab", "toh", "ka", "ke", "ki", "ko", "se", "mein"
}

HOOK_WORDS = {
    "secret", "mistake", "truth", "why", "how", "stop", "never", "always",
    "proven", "crazy", "warning", "trick", "insane", "hack", "nobody", "shocking",
    "raaz", "galti", "sach", "kyun", "kaise", "asliyat", "dekho", "zaroori"
}


def is_valid_story_ending(sentence: Dict[str, Any]) -> bool:
    """Ensure a sentence provides a complete, resolved thought and does not cut off mid-clause."""
    words = sentence.get("words", [])
    if not words:
        return False

    last_word_raw = words[-1].get("word", "").strip()
    last_token = re.sub(r"[^\w]", "", last_word_raw).lower()

    if last_token in UNRESOLVED_ENDINGS:
        return False

    if len(words) >= 2:
        last_two = " ".join(re.sub(r"[^\w]", "", w["word"]).lower() for w in words[-2:])
        if last_two in {"such as", "for example", "meaning that", "and then", "and also", "as well"}:
            return False

    if (
        last_word_raw.endswith(",")
        or last_word_raw.endswith(":")
        or last_word_raw.endswith(";")
        or last_word_raw.endswith("...")
        or last_word_raw.endswith("—")
    ):
        return False

    return True


def score_sentence_hook_strength(sentence: Dict[str, Any]) -> float:
    """Evaluate hook strength of an opening sentence (0.0 to 10.0)."""
    text = sentence.get("text", "").lower()
    words = sentence.get("words", [])
    if is_filler_or_weak_start(words):
        return 0.5

    score = 4.0
    if "?" in text:
        score += 3.5
    elif "!" in text:
        score += 1.5

    for hw in HOOK_WORDS:
        if hw in text:
            score += 2.0
            break

    if re.search(r"\b\d+\b", text):
        score += 1.5

    return min(10.0, score)


def is_filler_or_weak_start(first_words: List[Dict[str, Any]]) -> bool:
    """Detect if the opening words consist of filler, greeting, or mid-thought conjunction."""
    if not first_words:
        return True

    opening_text = " ".join(w["word"] for w in first_words[:4]).lower().strip()
    first_token = re.sub(r"[^\w]", "", first_words[0]["word"].lower())

    # Check mid-thought starters
    if first_token in MID_THOUGHT_STARTERS and len(first_words) > 1:
        return True

    # Check filler openers
    for filler in FILLER_OPENERS:
        if opening_text.startswith(filler):
            return True

    return False


def extract_sentences(raw_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group words into sentence units with precise start, end, and word lists."""
    all_words: List[Dict[str, Any]] = []
    for seg in raw_segments:
        words = seg.get("words", [])
        if words:
            all_words.extend(words)
        else:
            txt = seg.get("text", "").strip()
            if txt:
                all_words.append({
                    "word": txt,
                    "start": seg.get("start", 0.0),
                    "end": seg.get("end", 0.0),
                    "probability": 1.0,
                })

    if not all_words:
        return []

    sentences: List[Dict[str, Any]] = []
    current_words: List[Dict[str, Any]] = []

    for i, w in enumerate(all_words):
        current_words.append(w)
        word_text = w.get("word", "")

        has_pause = False
        if i + 1 < len(all_words):
            gap = all_words[i + 1]["start"] - w["end"]
            if gap > 0.75:
                has_pause = True

        ends_with_punct = any(word_text.endswith(p) for p in [".", "!", "?", "।"])
        clean_token = re.sub(r"[^\w]", "", word_text).lower()

        is_break = False
        if ends_with_punct:
            is_break = True
        elif has_pause:
            gap = all_words[i + 1]["start"] - w["end"]
            if gap > 1.2 and clean_token not in UNRESOLVED_ENDINGS:
                is_break = True
        elif i == len(all_words) - 1:
            is_break = True

        if is_break:
            sent_start = current_words[0]["start"]
            sent_end = current_words[-1]["end"]
            sent_text = " ".join(cw["word"] for cw in current_words).strip()

            sentences.append({
                "start": round(sent_start, 3),
                "end": round(sent_end, 3),
                "duration": round(sent_end - sent_start, 2),
                "text": sent_text,
                "words": list(current_words),
            })
            current_words = []

    return sentences


def generate_candidate_segments(
    transcript: Dict[str, Any],
    min_duration: float = MIN_CLIP_DURATION,
    max_duration: float = MAX_CLIP_DURATION,
    target_duration: float = TARGET_CLIP_DURATION,
) -> List[Dict[str, Any]]:
    """Extract candidate segments where the first 1-3 seconds form a hook and the ending
    resolves on a complete, self-contained story arc with 0.45s tail buffer.
    """
    raw_segments = transcript.get("segments", [])
    sentences = extract_sentences(raw_segments)

    if not sentences:
        return []

    candidates: List[Dict[str, Any]] = []
    num_sentences = len(sentences)

    for i in range(num_sentences):
        start_sentence = sentences[i]
        
        # Filter out filler or mid-thought openings
        if is_filler_or_weak_start(start_sentence["words"]):
            # Allow sentence only if it contains a strong question or exclamation hook
            if not any(p in start_sentence["text"] for p in ["?", "!"]):
                continue

        # Hook Realignment: If current sentence is weak/introductory and next sentence is a strong hook,
        # prefer starting directly on the strongest hook sentence
        if i + 1 < num_sentences:
            curr_hook = score_sentence_hook_strength(start_sentence)
            next_hook = score_sentence_hook_strength(sentences[i + 1])
            if curr_hook < 4.0 and next_hook >= 5.5:
                continue

        accumulated_words: List[Dict[str, Any]] = []
        start_time = start_sentence["start"]

        for j in range(i, num_sentences):
            accumulated_words.extend(sentences[j]["words"])
            raw_end_time = sentences[j]["end"]
            # Hold 0.45s tail silence after last word for a natural non-abrupt ending
            padded_end_time = round(raw_end_time + 0.45, 3)
            duration = padded_end_time - start_time

            if duration > max_duration:
                break

            if duration >= min_duration:
                # Proper Story Ending Check: Reject dangling clauses and incomplete thoughts
                if not is_valid_story_ending(sentences[j]):
                    continue

                sentence_count = (j - i + 1)
                # If the opening sentence was an intriguing question, ensure the clip spans enough sentences
                # to provide the full answer/story rather than cutting off as a cliffhanger
                if "?" in start_sentence["text"] and sentence_count < 2 and duration < 20.0:
                    continue

                text_content = " ".join(w["word"] for w in accumulated_words).strip()
                
                # Check for context dependency penalties
                has_dep = any(dep in text_content.lower() for dep in DEPENDENT_PHRASES)

                candidates.append({
                    "start": round(start_time, 2),
                    "end": round(padded_end_time, 2),
                    "duration": round(duration, 2),
                    "text": text_content,
                    "words": list(accumulated_words),
                    "sentence_count": sentence_count,
                    "has_dependency": has_dep,
                    "opening_sentence": start_sentence["text"],
                    "ending_sentence": sentences[j]["text"],
                })

    return candidates


def filter_overlapping_candidates(candidates: List[Dict[str, Any]], max_iou: float = 0.7) -> List[Dict[str, Any]]:
    """Filter out candidate segments that heavily overlap in time."""
    if not candidates:
        return []
    kept: List[Dict[str, Any]] = []
    for cand in candidates:
        overlaps = False
        for k in kept:
            inter = max(0.0, min(cand["end"], k["end"]) - max(cand["start"], k["start"]))
            union = (cand["end"] - cand["start"]) + (k["end"] - k["start"]) - inter
            iou = inter / union if union > 0 else 0.0
            if iou > max_iou:
                overlaps = True
                break
        if not overlaps:
            kept.append(cand)
    return kept
