"""
Gallery image downloader service.

Scrapes image URLs from a gallery page and downloads them to a local directory.
Uses httpx for HTTP requests (better TLS/SSL compatibility than urllib).
"""

import os
import re

import time

import httpx
import structlog

log = structlog.get_logger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_MAX_RETRIES = 10


def _fetch_with_retry(url: str) -> httpx.Response:
    """Fetch a URL with retries on connection errors."""
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            with httpx.Client(headers=_HEADERS, follow_redirects=True, timeout=_TIMEOUT) as client:
                resp = client.get(url)
                resp.raise_for_status()
                return resp
        except Exception as e:
            if attempt == _MAX_RETRIES:
                raise
            delay = 2 + attempt
            log.warning("downloader.retry", url=url[:80], attempt=attempt, max=_MAX_RETRIES, error=str(e)[:60])
            time.sleep(delay)


def scrape_image_urls(page_url: str) -> list[str]:
    """Fetch a gallery page and extract full-resolution image URLs."""
    resp = _fetch_with_retry(page_url)
    html = resp.text

    # Pattern 1: pornpics.com — <a class='rel-link' href='https://cdni.pornpics.com/1280/...'>
    urls = re.findall(r"<a[^>]+class=['\"]rel-link['\"][^>]+href=['\"]([^'\"]+)['\"]", html)

    # Pattern 2: generic — find all image URLs in <a> or <img> tags
    if not urls:
        urls = re.findall(r'href=["\']?(https?://[^"\'>\s]+\.(?:jpg|jpeg|png|webp))["\']?', html, re.IGNORECASE)

    # Pattern 3: data-src attributes (lazy loaded images)
    if not urls:
        urls = re.findall(r'data-src=["\']?(https?://[^"\'>\s]+\.(?:jpg|jpeg|png|webp))["\']?', html, re.IGNORECASE)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)

    log.info("downloader.scraped", url=page_url, images_found=len(unique))
    return unique


def download_images(
    image_urls: list[str],
    dest_dir: str,
    on_progress: callable = None,
) -> dict:
    """Download images to dest_dir. Returns stats dict."""
    os.makedirs(dest_dir, exist_ok=True)

    downloaded = 0
    failed = 0
    total_bytes = 0
    errors = []

    for i, url in enumerate(image_urls):
        # Extract filename from URL
        filename = url.split("/")[-1].split("?")[0]
        if not filename:
            filename = f"image_{i:04d}.jpg"

        dest_path = os.path.join(dest_dir, filename)

        # Skip if already exists
        if os.path.exists(dest_path):
            downloaded += 1
            if on_progress:
                on_progress(i + 1, len(image_urls), filename, "skipped")
            continue

        try:
            resp = _fetch_with_retry(url)
            data = resp.content

            with open(dest_path, "wb") as f:
                f.write(data)

            downloaded += 1
            total_bytes += len(data)
            if on_progress:
                on_progress(i + 1, len(image_urls), filename, "done")
        except Exception as e:
            failed += 1
            errors.append(f"{filename}: {e}")
            log.warning("downloader.image_failed", url=url, error=str(e))
            if on_progress:
                on_progress(i + 1, len(image_urls), filename, "error")

    return {
        "downloaded": downloaded,
        "failed": failed,
        "total_bytes": total_bytes,
        "total_images": len(image_urls),
        "errors": errors,
    }
