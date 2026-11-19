"""Review sheet management and clip approval workflow."""

from pathlib import Path
from typing import List, Dict, Any, Optional
import csv
from datetime import datetime

from clipwise.config import OUTPUT_DIR, LOG_FILE

CSV_HEADERS = ["clip_id", "start", "end", "duration", "hook_score", "title", "status"]


def init_review_sheet(video_output_dir: Path, clips: List[Dict[str, Any]]) -> Path:
    """Create or update review.csv in the video output folder with initial 'pending' status."""
    csv_path = video_output_dir / "review.csv"

    # If already exists, preserve approved/rejected decisions
    existing_status = {}
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_status[row["clip_id"]] = row.get("status", "pending")

    rows = []
    for c in clips:
        cid = c["clip_id"]
        status = existing_status.get(cid, "pending")
        rows.append({
            "clip_id": cid,
            "start": str(c["start"]),
            "end": str(c["end"]),
            "duration": str(c["duration"]),
            "hook_score": str(c.get("hook_score", 0.0)),
            "title": c.get("title", ""),
            "status": status,
        })

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)

    return csv_path


def load_review_sheet(video_output_dir: Path) -> List[Dict[str, str]]:
    """Read review.csv into a list of dicts."""
    csv_path = video_output_dir / "review.csv"
    if not csv_path.exists():
        return []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def set_clip_status(clip_id: str, new_status: str, video_id: Optional[str] = None) -> bool:
    """Mark a clip as 'approved' or 'rejected'.
    
    If video_id is not given, searches across all output folders.
    """
    valid_statuses = {"pending", "approved", "rejected"}
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid status '{new_status}'. Must be one of {valid_statuses}")

    target_dirs = [OUTPUT_DIR / video_id] if video_id else list(OUTPUT_DIR.iterdir())
    updated = False

    for vdir in target_dirs:
        if not vdir.is_dir():
            continue
        csv_path = vdir / "review.csv"
        if not csv_path.exists():
            continue

        rows = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        matched = False
        for row in rows:
            if row["clip_id"] == clip_id:
                row["status"] = new_status
                matched = True
                updated = True

        if matched:
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
                writer.writeheader()
                writer.writerows(rows)

    return updated


def get_all_pending_clips() -> List[Dict[str, str]]:
    """Retrieve all clips across all output folders with status 'pending'."""
    pending = []
    if not OUTPUT_DIR.exists():
        return pending

    for vdir in sorted(OUTPUT_DIR.iterdir()):
        if not vdir.is_dir():
            continue
        csv_path = vdir / "review.csv"
        if not csv_path.exists():
            continue

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("status") == "pending":
                    row["video_id"] = vdir.name
                    pending.append(row)

    return pending


def append_to_run_log(
    video_id: str,
    url: str,
    clip_count: int,
    status: str = "SUCCESS",
    details: str = "",
    source_type: str = "youtube",
    ownership_confirmed: bool = True,
):
    """Log pipeline run event, uploads, and ownership confirmations to clipwise_log.csv."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    file_exists = LOG_FILE.exists()

    headers = [
        "timestamp",
        "video_id",
        "source_type",
        "url_or_file",
        "ownership_confirmed",
        "clips_generated",
        "status",
        "details",
    ]
    row = {
        "timestamp": datetime.now().isoformat(),
        "video_id": video_id,
        "source_type": source_type,
        "url_or_file": url,
        "ownership_confirmed": "YES" if ownership_confirmed else "NO",
        "clips_generated": str(clip_count),
        "status": status,
        "details": details,
    }

    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def create_approved_clips_zip(video_id: str) -> Optional[Path]:
    """Package only 'approved' clips (mp4, srt, and metadata.json) into a downloadable ZIP."""
    import zipfile
    video_dir = OUTPUT_DIR / video_id
    if not video_dir.exists():
        return None

    csv_path = video_dir / "review.csv"
    if not csv_path.exists():
        return None

    approved_clip_ids = set()
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("status") == "approved":
                approved_clip_ids.add(row["clip_id"])

    if not approved_clip_ids:
        return None

    zip_path = video_dir / f"{video_id}_approved_clips.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for cid in approved_clip_ids:
            for ext in [".mp4", ".srt", "_metadata.json", ".ass"]:
                target_file = video_dir / f"{cid}{ext}"
                if target_file.exists():
                    zf.write(target_file, arcname=f"{cid}/{target_file.name}")

    return zip_path
