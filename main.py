"""Clipwise CLI: Turn long YouTube videos into viral vertical short clips."""

import argparse
import sys
import json
from pathlib import Path
from typing import Optional

from clipwise.config import (
    ensure_ffmpeg,
    OUTPUT_DIR,
    DEFAULT_MAX_CLIPS,
    DEFAULT_RENDER_MODE,
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
)


def run_pipeline(
    url: str,
    max_clips: int = DEFAULT_MAX_CLIPS,
    force: bool = False,
    mode: str = DEFAULT_RENDER_MODE,
    use_llm: bool = False,
    progress_callback=None,
):
    """Run full end-to-end processing pipeline for a single YouTube video."""
    ensure_ffmpeg()

    def notify(step: str, percent: int, message: str):
        if progress_callback:
            progress_callback(step, percent, message)
        else:
            print(f"[{percent:3d}%] [{step.upper()}] {message}")

    notify("validate", 5, f"Validating YouTube URL: {url}")
    video_id = validate_youtube_url(url)
    video_output_dir = OUTPUT_DIR / video_id
    video_output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Download Video & Audio
    notify("download", 15, "Downloading video and extracting audio via yt-dlp...")
    video_file, audio_file, metadata = download_video(url, force=force)
    notify("download", 30, f"Downloaded '{metadata.get('title', '')}' ({metadata.get('duration', 0)}s)")

    # 2. Transcribe Audio
    notify("transcribe", 40, "Transcribing speech and extracting word timestamps with faster-whisper...")
    transcript_file = video_output_dir / "transcript.json"
    transcript = transcribe_audio(audio_file, output_path=transcript_file, force=force)
    notify("transcribe", 60, f"Transcribed {len(transcript.get('segments', []))} speech segments")

    # 3. Candidate Segmentation
    notify("segment", 65, "Finding candidate segments aligned to sentence boundaries (15-60s)...")
    candidates = generate_candidate_segments(transcript)
    if not candidates:
        notify("error", 100, "No valid segments between 15 and 60 seconds found.")
        append_to_run_log(video_id, url, 0, "FAILED", "No valid speech segments found")
        return []

    # 4. Hook Scoring & Ranking
    notify("score", 70, f"Scoring hook potential for {len(candidates)} candidates...")
    top_candidates = score_candidates(candidates, use_llm=use_llm, top_n=max_clips)
    notify("score", 75, f"Selected top {len(top_candidates)} engaging clips")

    # 5. Render Clips & Captions
    clips_info = []
    total = len(top_candidates)

    for idx, cand in enumerate(top_candidates, start=1):
        clip_id = f"{video_id}_clip_{idx:02d}"
        notify("render", 75 + int((idx / total) * 20), f"Rendering clip {idx}/{total}: {clip_id} (Score: {cand['hook_score']}/10)...")

        clip_mp4 = video_output_dir / f"{clip_id}.mp4"
        clip_srt = video_output_dir / f"{clip_id}.srt"
        clip_meta_file = video_output_dir / f"{clip_id}_metadata.json"

        # Generate metadata
        meta = create_clip_metadata(cand, metadata, clip_id)
        with open(clip_meta_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        # Render 9:16 vertical video with burned-in subtitles
        render_clip(
            source_video=video_file,
            candidate=cand,
            output_mp4=clip_mp4,
            output_srt=clip_srt,
            mode=mode,
            burn_captions=True,
            force=force,
        )

        clips_info.append({
            "clip_id": clip_id,
            "start": cand["start"],
            "end": cand["end"],
            "duration": cand["duration"],
            "hook_score": cand["hook_score"],
            "title": meta["title"],
            "mp4": str(clip_mp4),
            "srt": str(clip_srt),
            "metadata": meta,
        })

    # 6. Initialize Review Sheet & Log
    init_review_sheet(video_output_dir, clips_info)
    append_to_run_log(video_id, url, len(clips_info), "SUCCESS", f"Generated {len(clips_info)} clips")

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
):
    """Run pipeline directly from an uploaded or local video file."""
    import subprocess
    ensure_ffmpeg()

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
    transcript_file = video_output_dir / "transcript.json"
    transcript = transcribe_audio(audio_file, output_path=transcript_file, force=force)
    notify("transcribe", 60, f"Transcribed {len(transcript.get('segments', []))} speech segments")

    notify("segment", 65, "Finding candidate segments aligned to sentence boundaries (15-60s)...")
    candidates = generate_candidate_segments(transcript)
    if not candidates:
        notify("error", 100, "No valid segments between 15 and 60 seconds found.")
        append_to_run_log(video_id, "upload", 0, "FAILED", "No valid speech segments found")
        return []

    notify("score", 70, f"Scoring hook potential for {len(candidates)} candidates...")
    top_candidates = score_candidates(candidates, use_llm=use_llm, top_n=max_clips)
    notify("score", 75, f"Selected top {len(top_candidates)} engaging clips")

    clips_info = []
    total = len(top_candidates)
    for idx, cand in enumerate(top_candidates, start=1):
        clip_id = f"{video_id}_clip_{idx:02d}"
        notify("render", 75 + int((idx / total) * 20), f"Rendering clip {idx}/{total}: {clip_id} (Score: {cand['hook_score']}/10)...")
        clip_mp4 = video_output_dir / f"{clip_id}.mp4"
        clip_srt = video_output_dir / f"{clip_id}.srt"
        clip_meta_file = video_output_dir / f"{clip_id}_metadata.json"

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
            force=force,
        )

        clips_info.append({
            "clip_id": clip_id,
            "start": cand["start"],
            "end": cand["end"],
            "duration": cand["duration"],
            "hook_score": cand["hook_score"],
            "title": meta["title"],
            "mp4": str(clip_mp4),
            "srt": str(clip_srt),
            "mp4_url": f"/media/{video_id}/{clip_id}.mp4",
            "srt_url": f"/media/{video_id}/{clip_id}.srt",
            "metadata": meta,
            "status": "pending",
        })

    init_review_sheet(video_output_dir, clips_info)
    append_to_run_log(video_id, "upload", len(clips_info), "SUCCESS", f"Generated {len(clips_info)} clips")
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
