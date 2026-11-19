"""Storage management, auto-cleanup, and versioned file paths for Clipwise v2."""

import time
import shutil
from pathlib import Path
from typing import Dict, Any, List

from clipwise.config import ORIGINALS_DIR, OUTPUT_DIR, ORIGINALS_TTL_DAYS


def clean_expired_originals(ttl_days: int = ORIGINALS_TTL_DAYS) -> int:
    """Remove original downloaded/uploaded videos older than ttl_days.
    
    Rendered clips in OUTPUT_DIR are NEVER deleted by this function.
    Returns the number of cleaned up items.
    """
    if ttl_days <= 0:
        return 0

    now = time.time()
    cutoff = now - (ttl_days * 86400)
    cleaned_count = 0

    if not ORIGINALS_DIR.exists():
        return 0

    for item in ORIGINALS_DIR.iterdir():
        try:
            mtime = item.stat().st_mtime
            if mtime < cutoff:
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
                cleaned_count += 1
        except Exception:
            pass

    return cleaned_count


def get_dir_size_bytes(path: Path) -> int:
    """Recursively calculate total bytes in a directory."""
    if not path.exists():
        return 0
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except Exception:
                pass
    return total


def get_storage_stats() -> Dict[str, Any]:
    """Return storage metrics in human-readable and byte formats."""
    originals_bytes = get_dir_size_bytes(ORIGINALS_DIR)
    output_bytes = get_dir_size_bytes(OUTPUT_DIR)

    total, used, free = shutil.disk_usage(str(OUTPUT_DIR.parent))

    return {
        "originals_bytes": originals_bytes,
        "originals_mb": round(originals_bytes / (1024 * 1024), 2),
        "output_bytes": output_bytes,
        "output_mb": round(output_bytes / (1024 * 1024), 2),
        "disk_free_gb": round(free / (1024 * 1024 * 1024), 2),
        "disk_total_gb": round(total / (1024 * 1024 * 1024), 2),
        "disk_used_percent": round((used / total) * 100, 1),
    }


def get_next_render_version(video_output_dir: Path) -> int:
    """Scan existing rendered clips to determine the next version number.
    
    Ensures every new pipeline execution writes fresh files and never serves
    stale cached mp4 files.
    """
    video_output_dir.mkdir(parents=True, exist_ok=True)
    existing_versions = [1]
    for p in video_output_dir.glob("*_v*_clip_*.mp4"):
        try:
            # Format: {id}_v{version}_clip_{idx}.mp4
            parts = p.stem.split("_v")
            if len(parts) > 1:
                v_part = parts[1].split("_clip_")[0]
                existing_versions.append(int(v_part))
        except Exception:
            pass
    return max(existing_versions) + 1
