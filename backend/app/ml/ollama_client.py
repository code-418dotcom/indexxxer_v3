"""
Stateless async HTTP client for Ollama LLM summarisation.

Generates a concise 2–3 sentence summary from a media item's caption and/or
transcript using the configured Ollama model (default: qwen2.5-coder:32b).

Usage:
    from app.ml.ollama_client import summarise
    summary = await summarise(caption="...", transcript="...", filename="img.jpg")
"""

from __future__ import annotations

import structlog
import httpx

from app.config import settings

log = structlog.get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are a concise media archivist. "
    "Given a filename plus any available caption or transcript, "
    "write a 2–3 sentence plain-English summary describing the content. "
    "Be factual and terse. Do not speculate beyond the provided text."
)


async def summarise(
    caption: str | None,
    transcript: str | None,
    filename: str,
) -> str:
    """
    Call Ollama and return a short summary string.

    At least one of *caption* or *transcript* should be non-empty.
    """
    parts = [f"Filename: {filename}"]
    if caption:
        parts.append(f"Caption: {caption}")
    if transcript:
        parts.append(f"Transcript (excerpt): {transcript[:1000]}")

    user_text = "\n".join(parts)

    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "stream": False,
    }

    log.info("ollama.request", model=settings.ollama_model, filename=filename)

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.ollama_url}/api/chat",
            json=payload,
        )
        response.raise_for_status()

    data = response.json()
    try:
        summary = data["message"]["content"].strip()
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"Unexpected Ollama response structure: {data}") from exc
    log.info("ollama.done", filename=filename, chars=len(summary))
    return summary
