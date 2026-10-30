"""Synthetic test images: smooth noise + shapes, so each one is distinct and photo-like."""
import io

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps


def make_image(seed: int, size=(640, 480)) -> Image.Image:
    rng = np.random.default_rng(seed)
    w, h = size
    base = np.zeros((h, w, 3), np.float32)
    for octave in (4, 8, 16, 32):
        small = rng.random((octave, int(octave * w / h) + 1, 3)).astype(np.float32)
        layer = np.asarray(Image.fromarray((small * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC),
                           np.float32)
        base += layer / octave
    base = (base - base.min()) / (np.ptp(base) or 1) * 255
    img = Image.fromarray(base.astype(np.uint8))
    d = ImageDraw.Draw(img)
    for _ in range(rng.integers(6, 14)):
        x0, y0 = rng.integers(0, w - 40), rng.integers(0, h - 40)
        x1, y1 = x0 + rng.integers(30, 260), y0 + rng.integers(30, 200)
        col = tuple(int(c) for c in rng.integers(0, 255, 3))
        (d.ellipse if rng.random() < 0.5 else d.rectangle)((x0, y0, x1, y1), fill=col)
    return img.filter(ImageFilter.GaussianBlur(1.2))


def jpeg(img, q):
    b = io.BytesIO()
    img.save(b, "JPEG", quality=q)
    return Image.open(io.BytesIO(b.getvalue())).convert("RGB")


def crop(img, f):
    w, h = img.size
    dx, dy = int(w * (1 - f) / 2), int(h * (1 - f) / 2)
    return img.crop((dx, dy, w - dx, h - dy))


def watermark(img):
    img = img.copy()
    d = ImageDraw.Draw(img)
    d.rectangle((0, img.height - 50, img.width, img.height), fill=(0, 0, 0))
    d.text((10, img.height - 40), "(c) some site  www.example.com", fill=(255, 255, 255))
    return img


TRANSFORMS = {
    "resize_25%": lambda i: i.resize((i.width // 4, i.height // 4)),
    "jpeg_q20": lambda i: jpeg(i, 20),
    "crop_85%": lambda i: crop(i, 0.85),
    "crop_70%": lambda i: crop(i, 0.70),
    "corner_crop_75%": lambda i: i.crop((0, 0, int(i.width * .75), int(i.height * .75))),
    "mirror": ImageOps.mirror,
    "brighter_40%": lambda i: ImageEnhance.Brightness(i).enhance(1.4),
    "contrast_low": lambda i: ImageEnhance.Contrast(i).enhance(0.6),
    "grayscale": lambda i: ImageOps.grayscale(i).convert("RGB"),
    "watermark_bar": watermark,
    "rotate_3deg": lambda i: i.rotate(3, expand=False, fillcolor=(0, 0, 0)),
    "letterbox": lambda i: ImageOps.pad(i, (i.width, i.height + 200), color=(0, 0, 0)),
    "stretched": lambda i: i.resize((i.width, int(i.height * 0.8))),
    "combo_resize+jpeg+mirror": lambda i: jpeg(ImageOps.mirror(i.resize((320, 240))), 40),
}
