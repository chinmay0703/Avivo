# vision service - takes uploaded images and generates captions + tags
# using BLIP model from huggingface (runs locally, no api needed)

import os, sys, io
import torch
from PIL import Image
from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic import BaseModel
from transformers import BlipProcessor, BlipForConditionalGeneration

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config

app = FastAPI(title="Vision Service")

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

# load blip model - takes a bit on first run since it downloads ~990mb
print("loading BLIP model...")
blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
blip_model.eval()
print("BLIP loaded")

# these prompts help extract different tags from the image
TAG_PROMPTS = [
    "this image shows",
    "the main subject is",
    "the setting is",
]


class DescriptionResponse(BaseModel):
    caption: str
    tags: list[str]


def generate_caption(image):
    inputs = blip_processor(image, return_tensors="pt")
    with torch.no_grad():
        output = blip_model.generate(**inputs, max_new_tokens=50)
    return blip_processor.decode(output[0], skip_special_tokens=True)


def generate_tags(image):
    # run blip with different conditional prompts to get varied keywords
    tags = set()
    stopwords = {"the", "and", "with", "that", "this", "for", "are", "was", "has", "its"}

    for prompt in TAG_PROMPTS:
        inputs = blip_processor(image, text=prompt, return_tensors="pt")
        with torch.no_grad():
            output = blip_model.generate(**inputs, max_new_tokens=20)
        result = blip_processor.decode(output[0], skip_special_tokens=True)

        # try to pull out useful words from the response
        result = result.strip().lower()
        words = result.replace(prompt.lower(), "").strip().split()
        for word in words:
            cleaned = word.strip(".,!?;:'\"()[]")
            if cleaned and len(cleaned) > 2 and cleaned not in stopwords:
                tags.add(cleaned)
                if len(tags) >= 5:
                    break
        if len(tags) >= 5:
            break

    tag_list = list(tags)[:3]
    # pad with generic tag if we didnt get enough
    while len(tag_list) < 3:
        tag_list.append("image")
    return tag_list[:3]


@app.post("/describe", response_model=DescriptionResponse)
async def describe_image(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"unsupported type: {file.content_type}")

    image_bytes = await file.read()
    if len(image_bytes) > 20 * 1024 * 1024:  # 20mb limit
        raise HTTPException(status_code=400, detail="image too large, max 20mb")

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    caption = generate_caption(image)
    tags = generate_tags(image)

    return DescriptionResponse(caption=caption, tags=tags)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "vision"}
