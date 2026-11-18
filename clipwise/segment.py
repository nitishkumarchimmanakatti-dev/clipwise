"""Candidate segment generator targeting 15 to 60 second windows aligned to sentences."""

from typing import List, Dict, Any
from clipwise.config import MIN_CLIP_DURATION, MAX_CLIP_DURATION, TARGET_CLIP_DURATION


def extract_sentences(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flatten segments and words into sentence-like units using punctuation and pauses."""
    all_words: List[Dict[str, Any]] = []
    for seg in segments:
        words = seg.get("words", [])
        if words:
            all_words.extend(words)
        else:
            # Fallback if word timestamps were unavailable
            all_words.append({
                "word": seg.get("text", "").strip(),
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
        
        # Check pause to next word
        has_pause = False
        if i + 1 < len(all_words):
            gap = all_words[i + 1]["start"] - w["end"]
            if gap > 0.8:
                has_pause = True

        ends_with_punct = any(word_text.endswith(p) for p in [".", "!", "?", "...", "—"])

        if ends_with_punct or has_pause or (i == len(all_words) - 1):
            sent_start = current_words[0]["start"]
            sent_end = current_words[-1]["end"]
            sent_text = " ".join(cw["word"] for cw in current_words).strip()
            
            sentences.append({
                "start": sent_start,
                "end": sent_end,
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
    """Create candidate windows between min_duration and max_duration on sentence boundaries."""
    raw_segments = transcript.get("segments", [])
    sentences = extract_sentences(raw_segments)

    if not sentences:
        return []

    candidates: List[Dict[str, Any]] = []
    num_sentences = len(sentences)

    for i in range(num_sentences):
        accumulated_words: List[Dict[str, Any]] = []
        start_time = sentences[i]["start"]

        for j in range(i, num_sentences):
            accumulated_words.extend(sentences[j]["words"])
            end_time = sentences[j]["end"]
            duration = end_time - start_time

            if duration > max_duration:
                break

            if duration >= min_duration:
                text_content = " ".join(w["word"] for w in accumulated_words).strip()
                candidates.append({
                    "start": round(start_time, 2),
                    "end": round(end_time, 2),
                    "duration": round(duration, 2),
                    "text": text_content,
                    "words": list(accumulated_words),
                    "sentence_count": (j - i + 1),
                })
                # If we've reached or slightly exceeded target_duration, move to next start
                if duration >= target_duration:
                    break

    # Deduplicate overlapping candidates (IoU > 0.70)
    filtered = filter_overlapping_candidates(candidates)

    # Resilient fallback: if no candidate reached min_duration (e.g. short trailer or brief speech)
    if not filtered:
        if sentences:
            first_start = sentences[0]["start"]
            last_end = sentences[-1]["end"]
            clip_start = max(0.0, first_start - 1.0)
            clip_end = max(clip_start + min_duration, last_end + 1.0)
            if (clip_end - clip_start) > max_duration:
                clip_end = clip_start + max_duration
            
            all_words = []
            for s in sentences:
                all_words.extend(s.get("words", []))

            filtered.append({
                "start": round(clip_start, 2),
                "end": round(clip_end, 2),
                "duration": round(clip_end - clip_start, 2),
                "text": " ".join(s["text"] for s in sentences).strip(),
                "words": all_words,
                "sentence_count": len(sentences),
            })
        else:
            # Fallback for purely visual/music content
            clip_dur = min(30.0, max(min_duration, transcript.get("duration", 30.0)))
            filtered.append({
                "start": 0.0,
                "end": round(clip_dur, 2),
                "duration": round(clip_dur, 2),
                "text": transcript.get("title", "High-Retention Visual Highlight"),
                "words": [],
                "sentence_count": 0,
            })

    return filtered


def filter_overlapping_candidates(candidates: List[Dict[str, Any]], max_iou: float = 0.70) -> List[Dict[str, Any]]:
    """Deduplicate candidates with excessive temporal overlap."""
    if not candidates:
        return []

    # Sort candidates by duration closeness to target (35s) or sentence count
    candidates_sorted = sorted(
        candidates,
        key=lambda c: abs(c["duration"] - TARGET_CLIP_DURATION)
    )

    selected: List[Dict[str, Any]] = []

    for cand in candidates_sorted:
        c_start = cand["start"]
        c_end = cand["end"]

        overlap_found = False
        for s in selected:
            s_start = s["start"]
            s_end = s["end"]

            # Calculate intersection and union
            inter_start = max(c_start, s_start)
            inter_end = min(c_end, s_end)
            intersection = max(0.0, inter_end - inter_start)

            union = (c_end - c_start) + (s_end - s_start) - intersection
            iou = intersection / union if union > 0 else 0.0

            if iou > max_iou:
                overlap_found = True
                break

        if not overlap_found:
            selected.append(cand)

    # Return in chronological order
    selected.sort(key=lambda c: c["start"])
    return selected
