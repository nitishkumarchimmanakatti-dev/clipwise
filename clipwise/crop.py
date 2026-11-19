"""Smart 9:16 video cropping with OpenCV face tracking for talking-head videos."""

from pathlib import Path
from typing import Optional, Tuple, List
import logging
import cv2

logger = logging.getLogger("clipwise.crop")


def detect_talking_head_face_x(
    video_path: Path,
    start_time: float,
    end_time: float,
    max_samples: int = 12,
) -> Optional[float]:
    """Sample frames across [start_time, end_time] and find smoothed horizontal face center.
    
    Returns:
        Horizontal pixel center of the speaker's face, or None if no face is detected.
    """
    if not video_path.exists():
        return None

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = end_time - start_time
    if duration <= 0:
        cap.release()
        return None

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    if face_cascade.empty():
        cap.release()
        return None

    # Calculate timestamps to sample
    step = duration / (max_samples + 1)
    sample_times = [start_time + step * (i + 1) for i in range(max_samples)]
    
    face_x_centers: List[float] = []

    for t in sample_times:
        frame_idx = int(t * fps)
        if total_frames > 0 and frame_idx >= total_frames:
            break

        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.15,
            minNeighbors=4,
            minSize=(60, 60),
        )

        if len(faces) > 0:
            # Pick the largest face (primary talking head)
            largest_face = max(faces, key=lambda b: b[2] * b[3])
            fx, fy, fw, fh = largest_face
            center_x = fx + (fw / 2.0)
            face_x_centers.append(center_x)

    cap.release()

    if not face_x_centers:
        return None

    # Apply smoothed median to reject temporary outliers / profile turns
    face_x_centers.sort()
    mid = len(face_x_centers) // 2
    if len(face_x_centers) % 2 == 0:
        smoothed_x = (face_x_centers[mid - 1] + face_x_centers[mid]) / 2.0
    else:
        smoothed_x = face_x_centers[mid]

    return smoothed_x


def get_smart_crop_filter(
    video_path: Path,
    start_time: float,
    end_time: float,
    target_width: int = 1080,
    target_height: int = 1920,
) -> Tuple[str, bool]:
    """Compute 9:16 vertical crop filter centered on detected speaker face.
    
    Returns:
        (ffmpeg_video_filter_fragment, has_detected_face)
        If has_detected_face is False, returns empty fragment so caller can use blurred fallback.
    """
    if not video_path.exists():
        return "", False

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return "", False

    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    cap.release()

    if src_w <= 0 or src_h <= 0:
        return "", False

    face_x = detect_talking_head_face_x(video_path, start_time, end_time)
    if face_x is None:
        return "", False

    # Compute 9:16 crop dimensions in source coordinate space
    target_aspect = target_width / target_height  # 9 / 16 = 0.5625
    src_aspect = src_w / src_h

    if src_aspect >= target_aspect:
        # Source is wider than 9:16 (standard 16:9 widescreen)
        crop_h = src_h
        crop_w = int(src_h * target_aspect)
        # Center crop window horizontally on the speaker's face
        crop_x = int(face_x - (crop_w / 2.0))
        # Clamp within source bounds
        crop_x = max(0, min(src_w - crop_w, crop_x))
        crop_y = 0
    else:
        # Source is narrower than 9:16
        crop_w = src_w
        crop_h = int(src_w / target_aspect)
        crop_x = 0
        crop_y = max(0, min(src_h - crop_h, int((src_h - crop_h) / 2.0)))

    # Ensure even dimensions for libx264
    crop_w = (crop_w // 2) * 2
    crop_h = (crop_h // 2) * 2
    crop_x = (crop_x // 2) * 2
    crop_y = (crop_y // 2) * 2

    filter_str = (
        f"[0:v]crop={crop_w}:{crop_h}:{crop_x}:{crop_y},"
        f"scale={target_width}:{target_height}[v0]"
    )
    return filter_str, True
