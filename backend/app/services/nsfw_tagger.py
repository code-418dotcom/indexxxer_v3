"""
HTTP client for the nsfw_ai_model_server.

The server reads files directly from disk (no upload needed).
Both containers share the /media volume mount.
"""

import httpx
import structlog

from app.config import settings

log = structlog.get_logger(__name__)

_TIMEOUT = httpx.Timeout(300.0, connect=10.0)  # videos can take a while


async def is_ready() -> bool:
    """Check if the NSFW tagger server is ready."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.get(f"{settings.nsfw_tagger_url}/ready")
            return resp.status_code == 200
    except Exception:
        return False


async def tag_video(file_path: str) -> dict | None:
    """
    Send a video to the NSFW tagger for analysis.
    Returns the raw result dict or None on failure.
    """
    payload = {
        "path": file_path,
        "frame_interval": settings.nsfw_tagger_frame_interval,
        "threshold": settings.nsfw_tagger_threshold,
        "return_confidence": True,
        "vr_video": False,
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{settings.nsfw_tagger_url}/v3/process_video/",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        log.error("nsfw_tagger.video_failed", path=file_path, error=str(exc))
        return None


async def tag_images(file_paths: list[str]) -> dict | None:
    """
    Send images to the NSFW tagger for analysis.
    Returns the raw result dict or None on failure.
    """
    payload = {
        "paths": file_paths,
        "threshold": settings.nsfw_tagger_threshold,
        "return_confidence": True,
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{settings.nsfw_tagger_url}/v3/process_images/",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        log.error("nsfw_tagger.images_failed", paths=file_paths, error=str(exc))
        return None


def extract_tags(result: dict) -> list[tuple[str, str, float]]:
    """
    Parse the tagger response and extract (tag_name, category, confidence) tuples.

    The response contains per-frame data with categories like:
    {"actions": [["blowjob", 0.95]], "bodyparts": [["Fingers", 0.8]], ...}

    We aggregate across all frames, keeping the max confidence per tag.
    """
    tag_map: dict[tuple[str, str], float] = {}  # (name, category) -> max_confidence

    # Handle both video (list of frame results) and image (single result) formats
    raw = result.get("result", result)

    # Normalize to list
    frames = raw if isinstance(raw, list) else [raw]

    for frame in frames:
        if not isinstance(frame, dict):
            continue
        for category in ("actions", "bdsm", "bodyparts", "positions"):
            items = frame.get(category, [])
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, list) and len(item) >= 2:
                    name, confidence = str(item[0]).strip().lower(), float(item[1])
                elif isinstance(item, str):
                    name, confidence = item.strip().lower(), 1.0
                else:
                    continue
                if not name:
                    continue
                key = (name, category)
                tag_map[key] = max(tag_map.get(key, 0.0), confidence)

    return [(name, cat, conf) for (name, cat), conf in tag_map.items()]
