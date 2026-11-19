"""Speech-to-text transcription with word-level timestamps using faster-whisper."""

from pathlib import Path
from typing import Dict, Any, List, Optional
import json
from faster_whisper import WhisperModel

from clipwise.config import WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE


def transcribe_audio(
    audio_path: Path,
    output_path: Optional[Path] = None,
    model_size: str = WHISPER_MODEL,
    force: bool = False,
) -> Dict[str, Any]:
    """Transcribe audio file using faster-whisper and capture word-level timestamps.
    
    Returns a dictionary containing:
        - full_text: complete transcribed text
        - segments: list of segments with start, end, text, and word-level details
    """
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file does not exist: {audio_path}")

    # Check if cached transcript exists
    if output_path and output_path.exists() and not force:
        with open(output_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # Initialize model
    model = WhisperModel(
        model_size,
        device=WHISPER_DEVICE,
        compute_type=WHISPER_COMPUTE_TYPE,
    )

    segments_generator, info = model.transcribe(
        str(audio_path),
        beam_size=1,
        best_of=1,
        word_timestamps=True,
        vad_filter=True,
    )

    segments_data: List[Dict[str, Any]] = []
    full_text_parts: List[str] = []

    for seg in segments_generator:
        words_list = []
        if seg.words:
            for w in seg.words:
                words_list.append({
                    "word": w.word.strip(),
                    "start": round(w.start, 3),
                    "end": round(w.end, 3),
                    "probability": round(w.probability, 3),
                })

        clean_text = seg.text.strip()
        if clean_text:
            full_text_parts.append(clean_text)

        segments_data.append({
            "id": seg.id,
            "start": round(seg.start, 3),
            "end": round(seg.end, 3),
            "text": clean_text,
            "words": words_list,
        })

    del model
    import gc
    gc.collect()

    transcript_result = {
        "language": info.language,
        "language_probability": round(info.language_probability, 3),
        "duration": round(info.duration, 2),
        "full_text": " ".join(full_text_parts),
        "segments": segments_data,
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(transcript_result, f, indent=2, ensure_ascii=False)

    return transcript_result
