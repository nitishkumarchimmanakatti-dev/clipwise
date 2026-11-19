"""Clipwise CLI: Turn long YouTube videos into viral vertical short clips."""

# Fix compatibility between faster-whisper and newer PyAV versions (14+)
try:
    import av
    _orig_av_open = av.open
    def _safe_av_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)
    av.open = _safe_av_open
except Exception:
    pass

import argparse
import sys
import json
import time
from pathlib import Path
from typing import Optional

from clipwise.config import (
    ensure_ffmpeg,
    OUTPUT_DIR,
    DEFAULT_MAX_CLIPS,
    DEFAULT_RENDER_MODE,
    DEFAULT_CAPTION_COLOR,
    MAX_ANALYSIS_SECONDS,
)
from clipwise.download import download_video, validate_youtube_url
from clipwise.transcribe import transcribe_audio
from clipwise.segment import generate_candidate_segments
from clipwise.score import score_candidates
from clipwise.render import render_clip
from clipwise.metadata import create_clip_metadata
from clipwise.review import (
    init_review_sheet,
    set_clip_status,
    get_all_pending_clips,
    append_to_run_log,
    log_pipeline_stage,
)
from clipwise.music import detect_clip_mood, get_track_for_mood
from clipwise.storage import get_next_render_version


def run_pipeline(
    url: str,
    max_clips: int = DEFAULT_MAX_CLIPS,
    force: bool = False,
    mode: str = DEFAULT_RENDER_MODE,
    use_llm: bool = False,
    progress_callback=None,
    ownership_confirmed: bool = True,
    rights_confirmed: bool = True,
    caption_color: str = DEFAULT_CAPTION_COLOR,
):
    """Run full end-to-end processing pipeline for a single YouTube video."""
    ensure_ffmpeg()

    if not (ownership_confirmed and rights_confirmed):
        raise ValueError("Processing refused: 'rights_confirmed' must be explicitly confirmed (True).")

    def notify(step: str, percent: int, message: str):
        if progress_callback:
            progress_callback(step, percent, message)
        else:
            print(f"[{percent:3d}%] [{step.upper()}] {message}")

    notify("validate", 5, f"Validating YouTube URL: {url}")
    video_id = validate_youtube_url(url, ownership_confirmed=ownership_confirmed)
    video_output_dir = OUTPUT_DIR / video_id
    video_output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Download Video & Audio
    notify("download", 15, "Downloading video and extracting audio via yt-dlp...")
    t_download = time.time()
    try:
        video_file, audio_file, metadata = download_video(
            url,
            force=force,
            ownership_confirmed=ownership_confirmed,
            rights_confirmed=rights_confirmed,
        )
        download_dur = time.time() - t_download
        log_pipeline_stage(video_id, "download", "SUCCESS", download_dur, f"Downloaded '{metadata.get('title', '')}'")
    except Exception as e:
        download_dur = time.time() - t_download
        log_pipeline_stage(video_id, "download", "FAILED", download_dur, str(e))
        raise

    video_dur = int(metadata.get('duration', 0))
    notify("download", 30, f"Downloaded '{metadata.get('title', '')}' ({video_dur}s)")
    if video_dur > MAX_ANALYSIS_SECONDS:
        notify("download", 35, f"Optimizing speed: Analyzing first 15 mins for hooks ({MAX_ANALYSIS_SECONDS}s / {video_dur}s)...")

    # 2. Transcribe Audio
    notify("transcribe", 40, f"Transcribing speech with faster-whisper ({min(video_dur, MAX_ANALYSIS_SECONDS)}s audio)...")
    t_transcribe = time.time()
    transcript_file = video_output_dir / "transcript.json"
    transcript = transcribe_audio(audio_file, output_path=transcript_file, force=force, progress_callback=notify)
    transcribe_dur = time.time() - t_transcribe

    # Explicit No-Speech Detection
    segments = transcript.get("segments", [])
    if not segments or not transcript.get("full_text", "").strip():
        log_pipeline_stage(video_id, "transcribe", "FAILED", transcribe_dur, "No speech detected")
        raise ValueError(
            "No speech detected in this video. Clipwise relies on spoken words to detect hooks and generate subtitles. "
            "Please upload a different video containing dialogue or speech."
        )

    log_pipeline_stage(video_id, "transcribe", "SUCCESS", transcribe_dur, f"Transcribed {len(segments)} segments")
    notify("transcribe", 60, f"Transcribed {len(segments)} speech segments")

    # 3. Candidate Segmentation
    notify("segment", 65, "Finding candidate segments aligned to sentence boundaries (15-60s)...")
    t_segment = time.time()
    candidates = generate_candidate_segments(transcript)
    if not candidates:
        segment_dur = time.time() - t_segment
        log_pipeline_stage(video_id, "segment", "FAILED", segment_dur, "No valid segments between 15 and 60 seconds found")
        notify("error", 100, "No valid segments between 15 and 60 seconds found.")
        append_to_run_log(
            video_id, url, 0, "FAILED", "No valid speech segments found",
            source_type="youtube", ownership_confirmed=ownership_confirmed,
        )
        return []

    # 4. Hook Scoring & Ranking
    notify("score", 70, f"Scoring hook potential for {len(candidates)} candidates...")
    top_candidates = score_candidates(candidates, use_llm=use_llm, top_n=max_clips)
    segment_dur = time.time() - t_segment
    log_pipeline_stage(video_id, "segment", "SUCCESS", segment_dur, f"Found {len(candidates)} candidates, ranked top {len(top_candidates)}")
    notify("score", 75, f"Selected top {len(top_candidates)} engaging clips")

    # 5. Render Clips & Captions
    clips_info = []
    total = len(top_candidates)
    version_id = get_next_render_version(video_output_dir)
    t_render = time.time()

    for idx, cand in enumerate(top_candidates, start=1):
        clip_id = f"{video_id}_v{version_id}_clip_{idx:02d}"
        render_pct_start = 75 + int(((idx - 0.7) / total) * 20)
        render_pct_done = 75 + int((idx / total) * 20)
        notify("render", render_pct_start, f"Rendering clip {idx}/{total}: {clip_id} (Score: {cand['hook_score']}/10)...")

        clip_mp4 = video_output_dir / f"{clip_id}.mp4"
        clip_srt = video_output_dir / f"{clip_id}.srt"
        clip_meta_file = video_output_dir / f"{clip_id}_metadata.json"

        # Detect situational background music
        mood, music_reason = detect_clip_mood(cand)
        cand["mood"] = mood
        cand["music_reason"] = music_reason
        music_track = get_track_for_mood(mood)
        cand["music_track"] = music_track
        cand["version"] = version_id

        # Generate metadata
        meta = create_clip_metadata(cand, metadata, clip_id)
        with open(clip_meta_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        # Render 9:16 vertical video with burned-in subtitles (placed in bottom blur zone) and ducked music
        render_clip(
            source_video=video_file,
            candidate=cand,
            output_mp4=clip_mp4,
            output_srt=clip_srt,
            mode=mode,
            burn_captions=True,
            force=True,
            caption_color=caption_color,
            music_track=music_track,
        )
        music_note = f" with {music_track['name']}" if music_track else " (no music)"
        notify("render", render_pct_done, f"✓ Rendered clip {idx}/{total}: {clip_id} ({int(cand['duration'])}s){music_note}")

        clips_info.append({
            "clip_id": clip_id,
            "start": cand["start"],
            "end": cand["end"],
            "duration": cand["duration"],
            "hook_score": cand["hook_score"],
            "why_this_clip": cand.get("why_this_clip", ""),
            "music_used": bool(music_track),
            "music_track": music_track.get("name") if music_track else None,
            "music_reason": music_reason,
            "title": meta["title"],
            "mp4": str(clip_mp4),
            "srt": str(clip_srt),
            "metadata": meta,
        })

    render_dur = time.time() - t_render
    log_pipeline_stage(video_id, "render", "SUCCESS", render_dur, f"Rendered {len(clips_info)} clips (v{version_id})")

    # 6. Initialize Review Sheet & Log
    init_review_sheet(video_output_dir, clips_info)
    append_to_run_log(
        video_id, url, len(clips_info), "SUCCESS", f"Generated {len(clips_info)} clips (v{version_id})",
        source_type="youtube", ownership_confirmed=ownership_confirmed,
    )

    notify("complete", 100, f"Complete! All clips saved to {video_output_dir}")
    return clips_info


def run_pipeline_for_file(
    video_file_path: Path,
    title: str = "Uploaded Video",
    max_clips: int = DEFAULT_MAX_CLIPS,
    force: bool = False,
    mode: str = DEFAULT_RENDER_MODE,
    use_llm: bool = False,
    progress_callback=None,
    rights_confirmed: bool = True,
    caption_color: str = DEFAULT_CAPTION_COLOR,
):
    """Run pipeline directly from an uploaded or local video file."""
    import subprocess
    ensure_ffmpeg()

    if not rights_confirmed:
        raise ValueError("Processing refused: 'rights_confirmed' must be explicitly confirmed (True).")

    def notify(step: str, percent: int, message: str):
        if progress_callback:
            progress_callback(step, percent, message)
        else:
            print(f"[{percent:3d}%] [{step.upper()}] {message}")

    import hashlib
    video_id = hashlib.md5(video_file_path.name.encode()).hexdigest()[:11]
    video_output_dir = OUTPUT_DIR / video_id
    video_output_dir.mkdir(parents=True, exist_ok=True)
    audio_file = video_output_dir / "audio.wav"

    notify("audio", 15, "Extracting audio from uploaded video...")
    cmd = [
        "ffmpeg", "-y", "-i", str(video_file_path),
        "-t", str(MAX_ANALYSIS_SECONDS),
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(audio_file)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Probe duration
    probe_cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(video_file_path)
    ]
    try:
        dur_res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        duration = float(dur_res.stdout.strip())
    except Exception:
        duration = 60.0

    metadata = {
        "id": video_id,
        "title": title,
        "duration": duration,
        "channel": "Upload",
        "webpage_url": "",
    }

    notify("transcribe", 40, "Transcribing speech and extracting word timestamps with faster-whisper...")
    t_transcribe = time.time()
    transcript_file = video_output_dir / "transcript.json"
    transcript = transcribe_audio(audio_file, output_path=transcript_file, force=force, progress_callback=notify)
    transcribe_dur = time.time() - t_transcribe

    # Explicit No-Speech Detection
    segments = transcript.get("segments", [])
    if not segments or not transcript.get("full_text", "").strip():
        log_pipeline_stage(video_id, "transcribe", "FAILED", transcribe_dur, "No speech detected")
        raise ValueError(
            "No speech detected in this video. Clipwise relies on spoken words to detect hooks and generate subtitles. "
            "Please upload a different video containing dialogue or speech."
        )

    log_pipeline_stage(video_id, "transcribe", "SUCCESS", transcribe_dur, f"Transcribed {len(segments)} segments")
    notify("transcribe", 60, f"Transcribed {len(segments)} speech segments")

    notify("segment", 65, "Finding candidate segments aligned to sentence boundaries (15-60s)...")
    t_segment = time.time()
    candidates = generate_candidate_segments(transcript)
    if not candidates:
        segment_dur = time.time() - t_segment
        log_pipeline_stage(video_id, "segment", "FAILED", segment_dur, "No valid speech segments found")
        notify("error", 100, "No valid segments between 15 and 60 seconds found.")
        append_to_run_log(
            video_id, title, 0, "FAILED", "No valid speech segments found",
            source_type="upload", ownership_confirmed=True,
        )
        return []

    notify("score", 70, f"Scoring hook potential for {len(candidates)} candidates...")
    top_candidates = score_candidates(candidates, use_llm=use_llm, top_n=max_clips)
    segment_dur = time.time() - t_segment
    log_pipeline_stage(video_id, "segment", "SUCCESS", segment_dur, f"Found {len(candidates)} candidates, ranked top {len(top_candidates)}")
    notify("score", 75, f"Selected top {len(top_candidates)} engaging clips")

    clips_info = []
    total = len(top_candidates)
    version_id = get_next_render_version(video_output_dir)
    t_render = time.time()

    for idx, cand in enumerate(top_candidates, start=1):
        clip_id = f"{video_id}_v{version_id}_clip_{idx:02d}"
        render_pct_start = 75 + int(((idx - 0.7) / total) * 20)
        render_pct_done = 75 + int((idx / total) * 20)
        notify("render", render_pct_start, f"Rendering clip {idx}/{total}: {clip_id} (Score: {cand['hook_score']}/10)...")
        clip_mp4 = video_output_dir / f"{clip_id}.mp4"
        clip_srt = video_output_dir / f"{clip_id}.srt"
        clip_meta_file = video_output_dir / f"{clip_id}_metadata.json"

        # Detect situational background music
        mood, music_reason = detect_clip_mood(cand)
        cand["mood"] = mood
        cand["music_reason"] = music_reason
        music_track = get_track_for_mood(mood)
        cand["music_track"] = music_track
        cand["version"] = version_id

        meta = create_clip_metadata(cand, metadata, clip_id)
        with open(clip_meta_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        render_clip(
            source_video=video_file_path,
            candidate=cand,
            output_mp4=clip_mp4,
            output_srt=clip_srt,
            mode=mode,
            burn_captions=True,
            force=True,
            caption_color=caption_color,
            music_track=music_track,
        )
        music_note = f" with {music_track['name']}" if music_track else " (no music)"
        notify("render", render_pct_done, f"✓ Rendered clip {idx}/{total}: {clip_id} ({int(cand['duration'])}s){music_note}")

        clips_info.append({
            "clip_id": clip_id,
            "start": cand["start"],
            "end": cand["end"],
            "duration": cand["duration"],
            "hook_score": cand["hook_score"],
            "why_this_clip": cand.get("why_this_clip", ""),
            "music_used": bool(music_track),
            "music_track": music_track.get("name") if music_track else None,
            "music_reason": music_reason,
            "title": meta["title"],
            "mp4": str(clip_mp4),
            "srt": str(clip_srt),
            "mp4_url": f"/media/video/{video_id}/{clip_id}.mp4",
            "srt_url": f"/media/download/{video_id}/{clip_id}.srt",
            "metadata": meta,
            "status": "pending",
        })

    render_dur = time.time() - t_render
    log_pipeline_stage(video_id, "render", "SUCCESS", render_dur, f"Rendered {len(clips_info)} clips (v{version_id})")

    init_review_sheet(video_output_dir, clips_info)
    append_to_run_log(
        video_id, title, len(clips_info), "SUCCESS", f"Generated {len(clips_info)} clips (v{version_id})",
        source_type="upload", ownership_confirmed=True,
    )
    notify("complete", 100, f"Complete! All clips saved to {video_output_dir}")
    return clips_info


def cli_review():
    """CLI handler for listing pending clips."""
    pending = get_all_pending_clips()
    if not pending:
        print("\n✨ No pending clips awaiting review! All caught up.")
        return

    print(f"\n📋 Pending Clips ({len(pending)} total):\n")
    print(f"{'CLIP ID':<25} | {'SCORE':<5} | {'DUR':<5} | {'TITLE'}")
    print("-" * 75)
    for row in pending:
        cid = row.get("clip_id", "")
        score = row.get("hook_score", "0.0")
        dur = f"{float(row.get('duration', 0)):.1f}s"
        title = row.get("title", "")
        print(f"{cid:<25} | {score:<5} | {dur:<5} | {title}")
    print("\nTo approve: python main.py approve <clip_id>")
    print("To reject:  python main.py reject <clip_id>")


def main():
    parser = argparse.ArgumentParser(
        description="Clipwise: Turn long YouTube videos into viral 9:16 vertical shorts."
    )
    subparsers = parser.add_subparsers(dest="command")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Process a YouTube video URL into shorts")
    run_parser.add_argument("url", type=str, help="YouTube video URL")
    run_parser.add_argument("--max-clips", type=int, default=DEFAULT_MAX_CLIPS, help="Max candidate clips to render")
    run_parser.add_argument("--mode", choices=["blur", "crop"], default=DEFAULT_RENDER_MODE, help="Vertical reformatting mode")
    run_parser.add_argument("--force", action="store_true", help="Overwrite existing output clips")
    run_parser.add_argument("--llm", action="store_true", help="Enable optional LLM hook scoring")

    # Command: review
    subparsers.add_parser("review", help="List pending clips awaiting approval")

    # Command: approve
    approve_parser = subparsers.add_parser("approve", help="Mark a clip as approved")
    approve_parser.add_argument("clip_id", type=str, help="ID of the clip to approve")

    # Command: reject
    reject_parser = subparsers.add_parser("reject", help="Mark a clip as rejected")
    reject_parser.add_argument("clip_id", type=str, help="ID of the clip to reject")

    # Command: ui / web
    ui_parser = subparsers.add_parser("ui", help="Launch the OpusClip-style Web Application")
    ui_parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface")
    ui_parser.add_argument("--port", type=int, default=8000, help="Port to run web app")

    args = parser.parse_args()

    # Startup checks
    try:
        ensure_ffmpeg()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.command == "run":
        try:
            run_pipeline(
                url=args.url,
                max_clips=args.max_clips,
                force=args.force,
                mode=args.mode,
                use_llm=args.llm,
            )
        except Exception as e:
            print(f"\n❌ Pipeline failed: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "review":
        cli_review()

    elif args.command == "approve":
        success = set_clip_status(args.clip_id, "approved")
        if success:
            print(f"✅ Clip '{args.clip_id}' approved.")
        else:
            print(f"❌ Clip '{args.clip_id}' not found.")

    elif args.command == "reject":
        success = set_clip_status(args.clip_id, "rejected")
        if success:
            print(f"🚫 Clip '{args.clip_id}' rejected.")
        else:
            print(f"❌ Clip '{args.clip_id}' not found.")

    elif args.command == "ui":
        from clipwise.app import start_server
        start_server(host=args.host, port=args.port)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
