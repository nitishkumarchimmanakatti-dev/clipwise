"""Metadata generator for YouTube Shorts (titles, descriptions, hashtags)."""

from typing import Dict, Any, List
import re


def generate_clip_title(text: str, max_chars: int = 68) -> str:
    """Generate a punchy YouTube Shorts title under max_chars length."""
    clean = text.strip()
    # If the text starts with a question, use the question
    if "?" in clean:
        first_q = clean.split("?")[0] + "?"
        if len(first_q) <= max_chars:
            return first_q

    # Find the first sentence
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    candidate_title = sentences[0] if sentences else clean

    if len(candidate_title) > max_chars:
        # Truncate at last whole word
        truncated = candidate_title[:max_chars - 3]
        last_space = truncated.rfind(" ")
        if last_space > 20:
            candidate_title = truncated[:last_space] + "..."
        else:
            candidate_title = truncated + "..."

    return candidate_title


def generate_hashtags(text: str) -> List[str]:
    """Generate 3 to 5 relevant hashtags for YouTube Shorts."""
    base_tags = ["#Shorts", "#Viral"]
    clean_lower = text.lower()

    topic_tags = {
        "coding": ["#Programming", "#Tech", "#DevLife"],
        "python": ["#Python", "#Coding", "#Software"],
        "ai": ["#ArtificialIntelligence", "#AI", "#TechNews"],
        "money": ["#Finance", "#Investing", "#Business"],
        "business": ["#Entrepreneur", "#Startup", "#Success"],
        "productivity": ["#Productivity", "#Mindset", "#Growth"],
        "fitness": ["#Fitness", "#Workout", "#Health"],
        "secret": ["#MindBlowing", "#Secrets", "#DidYouKnow"],
        "mistake": ["#LifeHacks", "#TipsAndTricks", "#Mistakes"],
    }

    added = 0
    for keyword, tags in topic_tags.items():
        if keyword in clean_lower:
            for t in tags:
                if t not in base_tags and len(base_tags) < 5:
                    base_tags.append(t)
                    added += 1
            if len(base_tags) >= 5:
                break

    if len(base_tags) < 4:
        base_tags.extend(["#Trending", "#YouTubeShorts"])

    return base_tags[:5]


def create_clip_metadata(
    candidate: Dict[str, Any],
    source_metadata: Dict[str, Any],
    clip_id: str,
) -> Dict[str, Any]:
    """Compile comprehensive metadata dictionary for an approved or candidate short."""
    start_sec = candidate["start"]
    end_sec = candidate["end"]
    duration = candidate["duration"]
    hook_score = candidate.get("hook_score", 5.0)

    part_num = candidate.get("part_number")
    total_parts = candidate.get("total_parts")

    if part_num:
        raw_title = generate_clip_title(candidate["text"], max_chars=55)
        title = f"Part {part_num} | {raw_title}"
    else:
        title = generate_clip_title(candidate["text"])

    hashtags = generate_hashtags(candidate["text"])

    source_title = source_metadata.get("title", "Source Video")
    channel_name = source_metadata.get("channel", "Unknown Channel")
    source_url = source_metadata.get("webpage_url", "")

    # Format timestamps mm:ss
    start_str = f"{int(start_sec // 60):02d}:{int(start_sec % 60):02d}"
    end_str = f"{int(end_sec // 60):02d}:{int(end_sec % 60):02d}"

    seq_prefix = f"Part {part_num} of {total_parts}\n" if (part_num and total_parts) else ""
    seq_note = (
        f"Follow the series in order! Watch Part {(part_num % total_parts) + 1} next.\n\n"
        if (part_num and total_parts and total_parts > 1)
        else ""
    )

    description = (
        f"{title}\n\n"
        f"{seq_prefix}"
        f"{seq_note}"
        f"Clip from '{source_title}' by {channel_name} ({start_str} - {end_str}).\n"
        f"Full video: {source_url}\n\n"
        f"{' '.join(hashtags)}"
    )

    metadata = {
        "clip_id": clip_id,
        "title": title,
        "part_number": part_num,
        "total_parts": total_parts,
        "description": description,
        "hashtags": hashtags,
        "start": start_sec,
        "end": end_sec,
        "duration": duration,
        "start_formatted": start_str,
        "end_formatted": end_str,
        "hook_score": hook_score,
        "why_this_clip": candidate.get("why_this_clip", "Strong standalone hook and narrative flow"),
        "music_used": bool(candidate.get("music_track")),
        "music_track": candidate.get("music_track", {}).get("name") if candidate.get("music_track") else None,
        "music_license": candidate.get("music_track", {}).get("license") if candidate.get("music_track") else None,
        "music_reason": candidate.get("music_reason", "Informational speech - no background music needed"),
        "version": candidate.get("version", 1),
        "source": {
            "title": source_title,
            "channel": channel_name,
            "url": source_url,
            "segment_range": f"{start_str} - {end_str}"
        },
        "rights_confirmed": bool(candidate.get("rights_confirmed", source_metadata.get("rights_confirmed", True))),
        "transcript_excerpt": candidate["text"]
    }

    return metadata
