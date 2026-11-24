"""FastAPI Web Server for Clipwise v2 - Professional Shorts Production Platform."""

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

from pathlib import Path
from typing import Dict, Any, Optional, List
import threading
import uuid
import json
import csv

from fastapi import FastAPI, HTTPException, Request, Response, UploadFile, File, Form, Depends, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from clipwise.config import (
    OUTPUT_DIR,
    ORIGINALS_DIR,
    DOWNLOADS_DIR,
    LOG_FILE,
    MAX_UPLOAD_SIZE_MB,
    ORIGINALS_TTL_DAYS,
    CLIPWISE_PASSWORD,
    DEFAULT_CAPTION_COLOR,
    ensure_ffmpeg,
)
from clipwise.auth import (
    generate_session_token,
    verify_session_token,
    is_authenticated,
    require_auth,
    COOKIE_NAME,
    SESSION_MAX_AGE,
)
from clipwise.download import validate_youtube_url
from clipwise.review import (
    set_clip_status,
    load_review_sheet,
    append_to_run_log,
    create_approved_clips_zip,
)
from clipwise.music import list_available_tracks, get_track_by_id, get_track_for_mood
from clipwise.storage import get_storage_stats, clean_expired_originals, get_next_render_version
from clipwise.render import render_clip
from clipwise.youtube_upload import (
    check_channel_auth_status,
    get_oauth_authorization_url,
    exchange_oauth_code,
    upload_clip_to_youtube,
    save_client_secret_file,
    is_youtube_configured,
)

try:
    from main import run_pipeline, run_pipeline_for_file
except ImportError:
    try:
        from clipwise.main import run_pipeline, run_pipeline_for_file
    except ImportError:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from main import run_pipeline, run_pipeline_for_file

app = FastAPI(title="Clipwise v2", description="High-Retention YouTube Shorts AI Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Background job tracking
tasks: Dict[str, Dict[str, Any]] = {}
cancelled_tasks = set()

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class LoginRequest(BaseModel):
    password: str


class GenerateRequest(BaseModel):
    url: str
    max_clips: int = 5
    mode: str = "blur"
    use_llm: bool = False
    force: bool = True
    ownership_confirmed: bool = False
    rights_confirmed: bool = False
    caption_color: str = DEFAULT_CAPTION_COLOR
    prompt: Optional[str] = None


class StatusUpdateRequest(BaseModel):
    status: str  # 'approved', 'rejected', 'pending'
    auto_upload: Optional[bool] = False


class YouTubeUploadRequest(BaseModel):
    video_id: str
    clip_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    privacy_status: Optional[str] = "public"


class YouTubeCredentialsRequest(BaseModel):
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    credentials_json: Optional[str] = None


class YouTubeCallbackRequest(BaseModel):
    code: str
    redirect_uri: Optional[str] = None


class MetadataUpdateRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    hashtags: Optional[List[str]] = None


class ReRenderRequest(BaseModel):
    start: float
    end: float
    caption_color: Optional[str] = DEFAULT_CAPTION_COLOR
    music_track_id: Optional[str] = None  # track_id or 'none'


class DeleteConfirmRequest(BaseModel):
    confirmation: str  # Must be "DELETE"


# --- AUTHENTICATION ROUTES ---

@app.get("/api/auth/status")
async def get_auth_status(request: Request):
    """Return whether authentication is required and if current user is logged in."""
    auth_req = bool(CLIPWISE_PASSWORD)
    logged_in = is_authenticated(request)
    return {"auth_required": auth_req, "logged_in": logged_in}


@app.post("/api/auth/login")
async def login(req: LoginRequest, response: Response):
    """Authenticate single-user admin password and set secure HTTP-only session cookie."""
    if not CLIPWISE_PASSWORD:
        return {"status": "ok", "message": "No password configured. Open access mode."}

    if req.password != CLIPWISE_PASSWORD:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password.")

    token = generate_session_token(req.password)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return {"status": "ok", "message": "Logged in successfully"}


@app.post("/api/auth/logout")
async def logout(response: Response):
    """Clear session cookie."""
    response.delete_cookie(COOKIE_NAME)
    return {"status": "ok", "message": "Logged out successfully"}


# --- STATIC ASSETS ---

@app.api_route("/robots.txt", methods=["GET", "HEAD"])
async def serve_robots():
    return FileResponse(STATIC_DIR / "robots.txt", media_type="text/plain")


@app.api_route("/sitemap.xml", methods=["GET", "HEAD"])
async def serve_sitemap():
    return FileResponse(STATIC_DIR / "sitemap.xml", media_type="application/xml")


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>Clipwise frontend not initialized</h1>", status_code=500)
    with open(index_file, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


# --- GENERATION & UPLOAD PIPELINE ---

@app.post("/api/generate")
async def start_generation(
    req: GenerateRequest,
    request: Request,
    _auth: None = Depends(require_auth),
):
    """Submit a YouTube URL for processing (requires ownership confirmation)."""
    if not (req.ownership_confirmed or req.rights_confirmed):
        raise HTTPException(
            status_code=400,
            detail="Rights confirmation required. You must check 'I own the rights to this video'."
        )

    try:
        ensure_ffmpeg()
        video_id = validate_youtube_url(req.url, ownership_confirmed=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "task_id": task_id,
        "video_id": video_id,
        "url": req.url,
        "status": "processing",
        "progress": 5,
        "current_step": "Initializing pipeline...",
        "logs": ["Job queued."],
        "clips": [],
        "error": None,
    }

    def worker():
        def on_progress(step: str, percent: int, msg: str):
            if task_id in cancelled_tasks:
                raise RuntimeError("Job cancelled by user.")
            tasks[task_id]["progress"] = percent
            tasks[task_id]["current_step"] = msg
            tasks[task_id]["logs"].append(f"[{percent}%] {msg}")

        try:
            clips = run_pipeline(
                url=req.url,
                max_clips=req.max_clips,
                force=req.force,
                mode=req.mode,
                use_llm=req.use_llm,
                progress_callback=on_progress,
                ownership_confirmed=True,
                rights_confirmed=True,
                caption_color=req.caption_color,
                prompt=req.prompt,
            )
            tasks[task_id]["status"] = "completed"
            tasks[task_id]["progress"] = 100
            tasks[task_id]["current_step"] = "Finished successfully!"
            tasks[task_id]["clips"] = clips
        except Exception as err:
            if task_id in cancelled_tasks:
                tasks[task_id]["status"] = "cancelled"
                tasks[task_id]["error"] = "Job cancelled by user"
                tasks[task_id]["logs"].append("Job cancelled.")
            else:
                err_str = str(err)
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["error"] = err_str
                tasks[task_id]["logs"].append(f"ERROR: {err_str}")

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    return {"task_id": task_id, "video_id": video_id}


@app.post("/api/upload")
async def upload_and_process_video(
    file: UploadFile = File(...),
    max_clips: int = Form(5),
    mode: str = Form("blur"),
    use_llm: bool = Form(False),
    caption_color: str = Form(DEFAULT_CAPTION_COLOR),
    prompt: Optional[str] = Form(None),
    _auth: None = Depends(require_auth),
):
    """Upload a local video file (MP4/MOV) with max upload size validation."""
    try:
        ensure_ffmpeg()
        task_id = str(uuid.uuid4())
        upload_dir = ORIGINALS_DIR / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)

        saved_file = upload_dir / f"{task_id}_{file.filename}"
        total_size = 0
        max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024

        with open(saved_file, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                total_size += len(chunk)
                if total_size > max_bytes:
                    saved_file.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"Video file exceeds maximum allowed size of {MAX_UPLOAD_SIZE_MB}MB."
                    )
                f.write(chunk)

        tasks[task_id] = {
            "task_id": task_id,
            "video_id": task_id[:11],
            "url": file.filename,
            "status": "processing",
            "progress": 5,
            "current_step": "Saved uploaded file, starting pipeline...",
            "logs": ["Job queued for uploaded file."],
            "clips": [],
            "error": None,
        }

        def upload_worker():
            def on_progress(step: str, percent: int, msg: str):
                if task_id in cancelled_tasks:
                    raise RuntimeError("Job cancelled by user.")
                tasks[task_id]["progress"] = percent
                tasks[task_id]["current_step"] = msg
                tasks[task_id]["logs"].append(f"[{percent}%] {msg}")

            try:
                clips = run_pipeline_for_file(
                    video_file_path=saved_file,
                    title=file.filename,
                    max_clips=max_clips,
                    force=True,
                    mode=mode,
                    use_llm=use_llm,
                    progress_callback=on_progress,
                    rights_confirmed=True,
                    caption_color=caption_color,
                    prompt=prompt,
                )
                tasks[task_id]["status"] = "completed"
                tasks[task_id]["progress"] = 100
                tasks[task_id]["current_step"] = "Finished successfully!"
                tasks[task_id]["clips"] = clips
            except Exception as err:
                if task_id in cancelled_tasks:
                    tasks[task_id]["status"] = "cancelled"
                    tasks[task_id]["error"] = "Job cancelled by user"
                else:
                    tasks[task_id]["status"] = "failed"
                    tasks[task_id]["error"] = str(err)
                    tasks[task_id]["logs"].append(f"ERROR: {err}")

        thread = threading.Thread(target=upload_worker, daemon=True)
        thread.start()

        return {"task_id": task_id, "video_id": task_id[:11]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/task/{task_id}")
async def get_task_status(task_id: str):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/api/task/{task_id}/cancel")
async def cancel_task(task_id: str, _auth: None = Depends(require_auth)):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    cancelled_tasks.add(task_id)
    tasks[task_id]["status"] = "cancelled"
    tasks[task_id]["current_step"] = "Cancelling..."
    return {"status": "ok", "message": f"Task {task_id} cancellation requested."}


# --- CLIPS & REVIEW WORKFLOW ---

@app.get("/api/history")
async def get_history():
    """List all processed videos and summary info."""
    if not OUTPUT_DIR.exists():
        return []

    history = []
    for vdir in sorted(OUTPUT_DIR.iterdir(), reverse=True):
        if not vdir.is_dir():
            continue
        video_id = vdir.name
        meta_file = DOWNLOADS_DIR / video_id / "metadata.json"
        title = video_id
        thumbnail = ""
        channel = ""

        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    title = meta.get("title", video_id)
                    thumbnail = meta.get("thumbnail", "")
                    channel = meta.get("channel", "")
            except Exception:
                pass

        clips = load_review_sheet(vdir)
        history.append({
            "video_id": video_id,
            "title": title,
            "channel": channel,
            "thumbnail": thumbnail,
            "clip_count": len(clips),
        })

    return history


@app.get("/api/clips/{video_id}")
async def get_clips_for_video(video_id: str):
    vdir = OUTPUT_DIR / video_id
    if not vdir.exists():
        raise HTTPException(status_code=404, detail="Video output not found")

    review_rows = load_review_sheet(vdir)
    status_map = {r["clip_id"]: r["status"] for r in review_rows}

    clips = []
    meta_files = sorted(vdir.glob("*_metadata.json"))
    for mf in meta_files:
        try:
            with open(mf, "r", encoding="utf-8") as f:
                cdata = json.load(f)
                cid = cdata["clip_id"]
                if cdata.get("youtube_status") == "uploaded":
                    cdata["status"] = "uploaded"
                else:
                    cdata["status"] = status_map.get(cid, "pending")
                cdata["video_url"] = f"/media/video/{video_id}/{cid}.mp4"
                cdata["srt_url"] = f"/media/download/{video_id}/{cid}.srt"
                cdata["download_url"] = f"/media/download/{video_id}/{cid}.mp4"
                clips.append(cdata)
        except Exception:
            continue

    return {"video_id": video_id, "clips": clips}


@app.post("/api/clips/{clip_id}/status")
async def update_clip_status_api(
    clip_id: str,
    req: StatusUpdateRequest,
    _auth: None = Depends(require_auth),
):
    success = set_clip_status(clip_id, req.status)
    if not success:
        raise HTTPException(status_code=404, detail="Clip not found")

    upload_result = None
    if req.status == "approved" and req.auto_upload:
        # Search for clip file across outputs
        for vdir in OUTPUT_DIR.iterdir():
            if not vdir.is_dir():
                continue
            meta_path = vdir / f"{clip_id}_metadata.json"
            if meta_path.exists():
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                clip_path = vdir / f"{clip_id}.mp4"
                if not clip_path.exists():
                    versioned = list(vdir.glob(f"{clip_id}_v*.mp4"))
                    if versioned:
                        versioned.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                        clip_path = versioned[0]
                if clip_path.exists():
                    try:
                        upload_result = upload_clip_to_youtube(
                            video_path=clip_path,
                            title=meta.get("title", "Viral Short"),
                            description=meta.get("description", ""),
                            tags=meta.get("hashtags", []),
                            privacy_status="public",
                        )
                        meta["youtube_video_id"] = upload_result.get("video_id")
                        meta["youtube_url"] = upload_result.get("url")
                        meta["youtube_uploaded_at"] = upload_result.get("uploaded_at")
                        meta["youtube_status"] = "uploaded"
                        set_clip_status(clip_id, "uploaded", video_id=vdir.name)
                        with open(meta_path, "w", encoding="utf-8") as f:
                            json.dump(meta, f, indent=2, ensure_ascii=False)
                    except Exception as ex:
                        print(f"[YouTube Auto-Upload Error] {ex}")
                        upload_result = {"error": str(ex)}
                break

    return {"clip_id": clip_id, "status": req.status, "upload": upload_result}


# --- YOUTUBE DATA API AUTOMATION ENDPOINTS ---

@app.get("/api/youtube/status")
async def get_youtube_status_api(_auth: None = Depends(require_auth)):
    """Check YouTube channel connection and return profile info."""
    return check_channel_auth_status()


@app.post("/api/youtube/auth/url")
async def get_youtube_auth_url_api(redirect_uri: str = "urn:ietf:wg:oauth:2.0:oob", _auth: None = Depends(require_auth)):
    """Get Google OAuth consent URL."""
    try:
        return get_oauth_authorization_url(redirect_uri)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/youtube/auth/callback")
async def handle_youtube_callback_api(req: YouTubeCallbackRequest, _auth: None = Depends(require_auth)):
    """Exchange OAuth code for tokens."""
    try:
        return exchange_oauth_code(req.code, req.redirect_uri or "urn:ietf:wg:oauth:2.0:oob")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/youtube/auth/credentials")
async def save_youtube_credentials_api(req: YouTubeCredentialsRequest, _auth: None = Depends(require_auth)):
    """Save client_secret.json or client ID/Secret."""
    try:
        if req.credentials_json:
            save_client_secret_file(req.credentials_json)
            return {"status": "ok", "message": "Saved client_secret.json successfully"}
        elif req.client_id and req.client_secret:
            cfg = {
                "installed": {
                    "client_id": req.client_id.strip(),
                    "client_secret": req.client_secret.strip(),
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
                }
            }
            save_client_secret_file(json.dumps(cfg))
            return {"status": "ok", "message": "Saved client credentials successfully"}
        else:
            raise HTTPException(status_code=400, detail="Missing credentials data.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/youtube/upload")
async def upload_to_youtube_api(req: YouTubeUploadRequest, _auth: None = Depends(require_auth)):
    """Upload a specific clip to YouTube Shorts."""
    video_dir = OUTPUT_DIR / req.video_id
    meta_path = video_dir / f"{req.clip_id}_metadata.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Clip metadata not found")

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    # Find the rendered clip file
    clip_path = video_dir / f"{req.clip_id}.mp4"
    if not clip_path.exists():
        versioned = list(video_dir.glob(f"{req.clip_id}_v*.mp4"))
        if versioned:
            versioned.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            clip_path = versioned[0]
        else:
            raise HTTPException(status_code=404, detail="Rendered clip video file not found")

    title = req.title or meta.get("title") or "Viral Short"
    description = req.description or meta.get("description") or ""
    tags = req.tags if req.tags is not None else meta.get("hashtags", [])
    privacy = req.privacy_status or "public"

    try:
        result = upload_clip_to_youtube(
            video_path=clip_path,
            title=title,
            description=description,
            tags=tags,
            privacy_status=privacy,
        )
        meta["youtube_video_id"] = result.get("video_id")
        meta["youtube_url"] = result.get("url")
        meta["youtube_uploaded_at"] = result.get("uploaded_at")
        meta["youtube_status"] = "uploaded"
        set_clip_status(req.clip_id, "uploaded", video_id=req.video_id)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"YouTube upload failed: {str(e)}")


@app.get("/api/youtube/uploaded")
async def get_all_uploaded_clips():
    """Retrieve all clips across all videos that have been uploaded to YouTube."""
    uploaded_clips = []
    if not OUTPUT_DIR.exists():
        return {"uploaded_clips": [], "count": 0}

    for vdir in OUTPUT_DIR.iterdir():
        if not vdir.is_dir():
            continue
        video_id = vdir.name
        meta_files = sorted(vdir.glob("*_metadata.json"))
        for mf in meta_files:
            try:
                with open(mf, "r", encoding="utf-8") as f:
                    cdata = json.load(f)
                if cdata.get("youtube_status") == "uploaded" or cdata.get("youtube_url"):
                    cid = cdata["clip_id"]
                    cdata["status"] = "uploaded"
                    cdata["video_url"] = f"/media/video/{video_id}/{cid}.mp4"
                    cdata["srt_url"] = f"/media/download/{video_id}/{cid}.srt"
                    cdata["download_url"] = f"/media/download/{video_id}/{cid}.mp4"
                    cdata["video_id"] = video_id
                    uploaded_clips.append(cdata)
            except Exception:
                continue

    # Sort newest uploads first
    uploaded_clips.sort(key=lambda c: c.get("youtube_uploaded_at") or "", reverse=True)
    return {"uploaded_clips": uploaded_clips, "count": len(uploaded_clips)}


@app.post("/api/clips/{video_id}/{clip_id}/metadata")
async def update_clip_metadata_api(
    video_id: str,
    clip_id: str,
    req: MetadataUpdateRequest,
    _auth: None = Depends(require_auth),
):
    """Update editable title, description, and hashtags in metadata.json."""
    meta_path = OUTPUT_DIR / video_id / f"{clip_id}_metadata.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Clip metadata not found")

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    meta["title"] = req.title
    if req.description:
        meta["description"] = req.description
    if req.hashtags is not None:
        meta["hashtags"] = req.hashtags

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    return {"status": "ok", "metadata": meta}


@app.post("/api/clips/{video_id}/{clip_id}/re-render")
async def rerender_clip_api(
    video_id: str,
    clip_id: str,
    req: ReRenderRequest,
    _auth: None = Depends(require_auth),
):
    """Re-trim start/end times and update music track/caption color for a clip."""
    video_dir = OUTPUT_DIR / video_id
    meta_path = video_dir / f"{clip_id}_metadata.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Clip metadata not found")

    # Find source video
    source_candidates = [
        ORIGINALS_DIR / video_id / "source.mp4",
        ORIGINALS_DIR / "uploads" / f"{video_id}.mp4",
    ]
    source_video = next((p for p in source_candidates if p.exists()), None)
    if not source_video:
        # Search uploads directory
        uploads_dir = ORIGINALS_DIR / "uploads"
        if uploads_dir.exists():
            matched = list(uploads_dir.glob(f"*{video_id}*"))
            if matched:
                source_video = matched[0]

    if not source_video or not source_video.exists():
        raise HTTPException(status_code=400, detail="Original source video not found on disk for re-rendering.")

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    # Determine music track
    music_track = None
    if req.music_track_id and req.music_track_id != "none":
        music_track = get_track_by_id(req.music_track_id)

    cand = {
        "start": req.start,
        "end": req.end,
        "duration": round(req.end - req.start, 2),
        "words": meta.get("words", []),
    }

    out_mp4 = video_dir / f"{clip_id}.mp4"
    out_srt = video_dir / f"{clip_id}.srt"

    render_clip(
        source_video=source_video,
        candidate=cand,
        output_mp4=out_mp4,
        output_srt=out_srt,
        mode="blur",
        burn_captions=True,
        force=True,
        caption_color=req.caption_color or DEFAULT_CAPTION_COLOR,
        music_track=music_track,
    )

    # Update metadata
    meta["start"] = req.start
    meta["end"] = req.end
    meta["duration"] = round(req.end - req.start, 2)
    meta["music_used"] = bool(music_track)
    meta["music_track"] = music_track.get("name") if music_track else None
    meta["music_license"] = music_track.get("license") if music_track else None
    meta["music_reason"] = "User override in review screen" if music_track else "No music (user selected)"

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    return {"status": "ok", "clip_id": clip_id, "metadata": meta}


@app.get("/api/clips/{video_id}/export-zip")
async def export_approved_clips_zip_api(video_id: str):
    """Download only approved clips as a ZIP archive."""
    zip_path = create_approved_clips_zip(video_id)
    if not zip_path or not zip_path.exists():
        raise HTTPException(status_code=400, detail="No approved clips found to export. Approve at least 1 clip first.")
    return FileResponse(zip_path, filename=f"{video_id}_approved_shorts.zip", media_type="application/zip")


# --- MUSIC & STORAGE ENDPOINTS ---

@app.get("/api/music/tracks")
async def get_available_music():
    """Return catalog of royalty-free situational background tracks."""
    return list_available_tracks()


@app.get("/api/storage")
async def get_storage_information(_auth: None = Depends(require_auth)):
    """Return storage metrics and quota usage."""
    return get_storage_stats()


@app.post("/api/storage/cleanup")
async def trigger_storage_cleanup(_auth: None = Depends(require_auth)):
    """Clean expired original videos older than ORIGINALS_TTL_DAYS."""
    cleaned = clean_expired_originals(ttl_days=ORIGINALS_TTL_DAYS)
    return {"status": "ok", "cleaned_items": cleaned}


@app.post("/api/video/{video_id}/delete")
async def delete_video_project(
    video_id: str,
    req: DeleteConfirmRequest,
    _auth: None = Depends(require_auth),
):
    """Safely delete a video project: requires typing 'DELETE' to confirm."""
    if req.confirmation != "DELETE":
        raise HTTPException(
            status_code=400,
            detail="Confirmation mismatch: You must type 'DELETE' to permanently delete this project."
        )

    import shutil
    out_dir = OUTPUT_DIR / video_id
    orig_dir = ORIGINALS_DIR / video_id

    if out_dir.exists():
        shutil.rmtree(out_dir, ignore_errors=True)
    if orig_dir.exists():
        shutil.rmtree(orig_dir, ignore_errors=True)

    return {"status": "ok", "message": f"Project {video_id} permanently deleted."}


@app.get("/api/log")
async def get_system_log(_auth: None = Depends(require_auth)):
    """Read run history log."""
    if not LOG_FILE.exists():
        return []
    rows = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return list(reversed(rows[-50:]))


# --- MEDIA STREAMING & DOWNLOADS ---

@app.get("/media/video/{video_id}/{filename}")
async def stream_video(video_id: str, filename: str):
    file_path = OUTPUT_DIR / video_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="video/mp4")


@app.get("/media/download/{video_id}/{filename}")
async def download_file(video_id: str, filename: str):
    file_path = OUTPUT_DIR / video_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=filename)


def start_server(host: str = "0.0.0.0", port: int = 8000):
    print(f"\n🚀 Launching Clipwise v2 Web App at http://{host}:{port}")
    uvicorn.run("clipwise.app:app", host=host, port=port, reload=False)
