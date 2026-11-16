"""FastAPI Web Server for Clipwise - OpusClip style web application."""

from pathlib import Path
from typing import Dict, Any, Optional
import threading
import uuid
import json

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from clipwise.config import OUTPUT_DIR, DOWNLOADS_DIR, ensure_ffmpeg
from clipwise.download import validate_youtube_url
from clipwise.review import set_clip_status, load_review_sheet, get_all_pending_clips
try:
    from main import run_pipeline
except ImportError:
    try:
        from clipwise.main import run_pipeline
    except ImportError:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from main import run_pipeline

app = FastAPI(title="Clipwise Web", description="Turn long YouTube videos into viral shorts")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Background job tracking
tasks: Dict[str, Dict[str, Any]] = {}

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class GenerateRequest(BaseModel):
    url: str
    max_clips: int = 5
    mode: str = "blur"  # 'blur' or 'crop'
    use_llm: bool = False
    force: bool = False


class StatusUpdateRequest(BaseModel):
    status: str  # 'approved', 'rejected', 'pending'


@app.get("/robots.txt")
async def serve_robots():
    return FileResponse(STATIC_DIR / "robots.txt", media_type="text/plain")


@app.get("/sitemap.xml")
async def serve_sitemap():
    return FileResponse(STATIC_DIR / "sitemap.xml", media_type="application/xml")


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>Clipwise frontend not initialized</h1>", status_code=500)
    with open(index_file, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.post("/api/generate")
async def start_generation(req: GenerateRequest, background_tasks: BackgroundTasks):
    try:
        ensure_ffmpeg()
        video_id = validate_youtube_url(req.url)
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
            )
            tasks[task_id]["status"] = "completed"
            tasks[task_id]["progress"] = 100
            tasks[task_id]["current_step"] = "Finished successfully!"
            tasks[task_id]["clips"] = clips
        except Exception as err:
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["error"] = str(err)
            tasks[task_id]["logs"].append(f"ERROR: {err}")

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    return {"task_id": task_id, "video_id": video_id}


@app.get("/api/task/{task_id}")
async def get_task_status(task_id: str):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


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
                cdata["status"] = status_map.get(cid, "pending")
                cdata["video_url"] = f"/media/video/{video_id}/{cid}.mp4"
                cdata["srt_url"] = f"/media/download/{video_id}/{cid}.srt"
                cdata["download_url"] = f"/media/download/{video_id}/{cid}.mp4"
                clips.append(cdata)
        except Exception:
            continue

    return {"video_id": video_id, "clips": clips}


@app.post("/api/clips/{clip_id}/status")
async def update_clip_status_api(clip_id: str, req: StatusUpdateRequest):
    success = set_clip_status(clip_id, req.status)
    if not success:
        raise HTTPException(status_code=404, detail="Clip not found")
    return {"clip_id": clip_id, "status": req.status}


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


def start_server(host: str = "127.0.0.1", port: int = 8000):
    print(f"\n🚀 Launching Clipwise Web App at http://{host}:{port}")
    uvicorn.run("clipwise.app:app", host=host, port=port, reload=False)
