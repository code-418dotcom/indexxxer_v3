"""
BLIP-2 image captioning model (Salesforce/blip2-opt-2.7b).

Lazy-loaded via the model registry. Uses float16 to fit in ~7 GB VRAM.
Model weights are cached in HF_HOME (Docker volume hf_models).

Usage:
    from app.ml.blip2_model import caption_image
    text = caption_image("/data/thumbnails/ab/abc123.jpg")
"""

from __future__ import annotations

import structlog

from app.ml.registry import registry

log = structlog.get_logger(__name__)

_MODEL_NAME = "blip2"


def _load_blip2():
    import torch
    from transformers import Blip2ForConditionalGeneration, Blip2Processor

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32

    log.info("blip2.loading", device=device, dtype=str(dtype))
    processor = Blip2Processor.from_pretrained("Salesforce/blip2-opt-2.7b")
    model = Blip2ForConditionalGeneration.from_pretrained(
        "Salesforce/blip2-opt-2.7b",
        torch_dtype=dtype,
        device_map=device,
    )
    model.eval()
    log.info("blip2.ready", device=device)
    return processor, model


def caption_image(image_path: str) -> str:
    """Return a text caption for the image at *image_path*."""
    import torch
    from PIL import Image

    processor, model = registry.get(_MODEL_NAME, _load_blip2)
    device = next(model.parameters()).device

    img = Image.open(image_path).convert("RGB")
    inputs = processor(images=img, return_tensors="pt").to(device)

    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=50)

    caption = processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
    log.debug("blip2.captioned", path=image_path, caption=caption[:80])
    return caption
