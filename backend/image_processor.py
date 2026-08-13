from io import BytesIO
from typing import List
from PIL import Image, ImageDraw
from entities import Match


def redact_image(image_bytes: bytes, matches: List[Match], fmt: str = "PNG") -> bytes:
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    pad = 3
    for m in matches:
        for box in m.boxes:
            x0, y0, x1, y1 = box
            draw.rectangle([x0 - pad, y0 - pad, x1 + pad, y1 + pad], fill=(0, 0, 0))
    out = BytesIO()
    img.save(out, format=fmt)
    return out.getvalue()


def image_dimensions(image_bytes: bytes):
    img = Image.open(BytesIO(image_bytes))
    return img.width, img.height
