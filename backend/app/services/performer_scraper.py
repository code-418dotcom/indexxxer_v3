"""
Freeones.com performer scraper.

Adapted from https://github.com/code-418dotcom/FOScraper
Uses Playwright for JS-rendered pages. Scrapes bio data and profile image.
Designed for single-performer lookups (by name or URL).
"""

from __future__ import annotations

import asyncio
import re
import structlog
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

log = structlog.get_logger(__name__)


def _clean(text: str | None) -> str:
    """Strip whitespace and normalise."""
    if not text:
        return ""
    return text.strip().replace("\n", " ")


def _name_to_slug(name: str) -> str:
    """Convert performer name to freeones URL slug: 'Mia Khalifa' -> 'mia-khalifa'."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


@dataclass
class ScrapedPerformer:
    """Raw scraped data from freeones.com."""

    name: str = ""
    image_url: str = ""
    image_bytes: bytes | None = None  # downloaded in-browser to avoid CDN issues
    bio_url: str = ""
    summary: str = ""
    extra: dict[str, str] = field(default_factory=dict)


async def scrape_performer_by_name(name: str) -> ScrapedPerformer | None:
    """
    Scrape a single performer's bio page from freeones.com.

    Tries the URL pattern: https://www.freeones.com/{name-slug}/bio
    Uses Playwright for JS-rendered content.
    """
    slug = _name_to_slug(name)
    bio_url = f"https://www.freeones.com/{slug}/bio"
    profile_url = f"https://www.freeones.com/{slug}"

    return await _scrape_bio_page(name, bio_url, profile_url)


async def scrape_performer_by_url(freeones_url: str) -> ScrapedPerformer | None:
    """
    Scrape a performer from a specific freeones URL.

    Accepts URLs like:
      - https://www.freeones.com/mia-khalifa
      - https://www.freeones.com/mia-khalifa/bio
      - https://www.freeones.com/mia-khalifa/videos
    """
    # Normalise to bio URL
    base = freeones_url.rstrip("/")
    # Strip any trailing path segment
    for suffix in ("/bio", "/videos", "/links", "/photos"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break

    bio_url = f"{base}/bio"
    return await _scrape_bio_page("", bio_url, base)


async def _scrape_bio_page(
    name: str, bio_url: str, profile_url: str
) -> ScrapedPerformer | None:
    """Core scraping logic using Playwright."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.error("performer_scraper.playwright_not_installed")
        return None

    result = ScrapedPerformer(name=name, bio_url=bio_url)

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()

            # First visit the profile page to get the image
            try:
                # Retry up to 3 times with backoff for transient connection resets
                for attempt in range(3):
                    try:
                        await page.goto(profile_url, timeout=30000)
                        break
                    except Exception:
                        if attempt == 2:
                            raise
                        await asyncio.sleep(2 * (attempt + 1))
                await page.wait_for_selector("body", timeout=10000)

                # Profile image: freeones uses img.img-fluid for the main photo.
                # Match by performer name in alt text first, then fall back to
                # first img.img-fluid on the page.
                performer_name = result.name or ""
                if performer_name:
                    img_el = await page.query_selector(
                        f'img.img-fluid[alt="{performer_name}"]'
                    )
                else:
                    img_el = None

                if not img_el:
                    img_el = await page.query_selector("img.img-fluid")

                if img_el:
                    result.image_url = await img_el.get_attribute("src") or ""
                    # Download image via browser's request context (avoids
                    # CORS restrictions and Docker CDN connectivity issues)
                    if result.image_url:
                        try:
                            api_ctx = page.context.request
                            resp = await api_ctx.get(result.image_url)
                            if resp.ok:
                                result.image_bytes = await resp.body()
                        except Exception as img_exc:
                            log.warning(
                                "performer_scraper.inline_image_failed",
                                error=str(img_exc),
                            )

                # Get name from page if not provided
                if not result.name:
                    name_el = await page.query_selector("h1")
                    if name_el:
                        result.name = _clean(await name_el.inner_text())

            except Exception as exc:
                log.warning(
                    "performer_scraper.profile_page_error",
                    url=profile_url,
                    error=str(exc),
                )

            # Now visit the bio page for detailed info
            try:
                for attempt in range(3):
                    try:
                        await page.goto(bio_url, timeout=30000)
                        break
                    except Exception:
                        if attempt == 2:
                            raise
                        await asyncio.sleep(2 * (attempt + 1))
                await page.wait_for_selector("body", timeout=10000)

                # Summary / about text
                summary_el = await page.query_selector("article p")
                if summary_el:
                    result.summary = _clean(await summary_el.inner_text())

                # Bio info pairs from profile-meta-list
                info_pairs = await page.query_selector_all(
                    "ul.profile-meta-list li"
                )
                for pair in info_pairs:
                    label_el = await pair.query_selector("span")
                    value_el = await pair.query_selector(
                        "a, span.font-size-xs"
                    )
                    label = _clean(await label_el.inner_text()) if label_el else ""
                    value = _clean(await value_el.inner_text()) if value_el else ""
                    if label and label.endswith(":"):
                        label = label[:-1]
                    if label and value and value != "Unknown":
                        result.extra[label] = value

            except Exception as exc:
                log.warning(
                    "performer_scraper.bio_page_error",
                    url=bio_url,
                    error=str(exc),
                )

            await browser.close()

    except Exception as exc:
        log.error("performer_scraper.failed", error=str(exc), exc_info=True)
        return None

    if not result.name:
        return None

    log.info(
        "performer_scraper.success",
        name=result.name,
        has_image=bool(result.image_url),
        fields=len(result.extra),
    )
    return result


async def save_performer_image(
    scraped: ScrapedPerformer, dest_path: Path
) -> bool:
    """Save performer profile image to local filesystem.

    Prefers pre-downloaded image_bytes (grabbed in-browser during scraping).
    Falls back to httpx download if bytes aren't available.
    """
    if scraped.image_bytes:
        try:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(scraped.image_bytes)
            log.info(
                "performer_scraper.image_saved",
                path=str(dest_path),
                size=len(scraped.image_bytes),
                method="inline",
            )
            return True
        except Exception as exc:
            log.error("performer_scraper.image_save_failed", error=str(exc))
            return False

    if not scraped.image_url:
        return False

    # Fallback: try httpx (may fail from Docker due to CDN connectivity)
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.freeones.com/",
        }
        async with httpx.AsyncClient(
            timeout=30, follow_redirects=True, headers=headers
        ) as client:
            resp = await client.get(scraped.image_url)
            resp.raise_for_status()
            dest_path.write_bytes(resp.content)
            log.info(
                "performer_scraper.image_saved",
                path=str(dest_path),
                size=len(resp.content),
                method="httpx",
            )
            return True
    except Exception as exc:
        log.error(
            "performer_scraper.image_download_failed",
            url=scraped.image_url,
            error=str(exc),
        )
        return False


def map_scraped_to_fields(scraped: ScrapedPerformer) -> dict[str, Any]:
    """
    Map scraped freeones data to Performer model fields.

    The freeones bio page uses labels like 'Birthdate', 'Birthplace',
    'Ethnicity', 'Hair Color', etc. Map these to our model columns.
    """
    field_map = {
        "Birthdate": "birthdate",
        "Birthday": "birthdate",
        "Date of Birth": "birthdate",
        "Birthplace": "birthplace",
        "Born": "birthplace",
        "Nationality": "nationality",
        "Ethnicity": "ethnicity",
        "Hair Color": "hair_color",
        "Hair Colour": "hair_color",
        "Eye Color": "eye_color",
        "Eye Colour": "eye_color",
        "Height": "height",
        "Weight": "weight",
        "Measurements": "measurements",
        "Cup Size": "measurements",
        "Years Active": "years_active",
        "Career Start And End": "years_active",
        "Active": "years_active",
    }

    result: dict[str, Any] = {}

    if scraped.summary:
        result["bio"] = scraped.summary

    for label, value in scraped.extra.items():
        model_field = field_map.get(label)
        if model_field and value:
            # Don't overwrite if we already have a value for this field
            if model_field not in result:
                result[model_field] = value

    return result
