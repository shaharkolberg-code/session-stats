"""Image fingerprints and similarity scoring.

Every candidate an engine returns is downloaded and compared against the
query image here. This is what turns "an engine said so" into a verified
match score, and it is the main source of the tool's accuracy.

Signals combined:
  * pHash (DCT)      - robust to resizing, compression, small edits
  * dHash (gradient) - robust to brightness/contrast changes
  * aHash (mean)     - cheap tie-breaker
  * HSV histogram    - catches recolours / grayscale versions
To survive crops and mirroring, each image is fingerprinted at several
crop windows plus a horizontal flip, and the best-matching pair wins.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageChops, ImageOps

Image.MAX_IMAGE_PIXELS = 120_000_000

# Crop windows as (left, top, right, bottom) fractions of the image.
_WINDOWS = [
    (0.0, 0.0, 1.0, 1.0),      # full image
    (0.1, 0.1, 0.9, 0.9),      # centre 80%
    (0.15, 0.15, 0.85, 0.85),  # centre 70%
    (0.2, 0.2, 0.8, 0.8),      # centre 60%
    (0.0, 0.0, 0.75, 0.75),    # corners at 75%
    (0.25, 0.0, 1.0, 0.75),
    (0.0, 0.25, 0.75, 1.0),
    (0.25, 0.25, 1.0, 1.0),
]

WEIGHTS = {"phash": 0.45, "dhash": 0.25, "ahash": 0.10, "color": 0.20}


def _dct_matrix(n: int) -> np.ndarray:
    k = np.arange(n)
    m = np.cos(np.pi * (2 * k[None, :] + 1) * k[:, None] / (2 * n))
    m[0] *= 1 / np.sqrt(2)
    return m * np.sqrt(2 / n)


_DCT32 = _dct_matrix(32)


def load_image(data: bytes | str) -> Image.Image:
    """Open image bytes or a path; fix EXIF rotation, flatten alpha, use frame 0."""
    img = Image.open(io.BytesIO(data) if isinstance(data, bytes) else data)
    try:
        img.seek(0)
    except EOFError:
        pass
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(bg, img)
    return img.convert("RGB")


def trim_borders(img: Image.Image, tolerance: int = 12) -> Image.Image:
    """Remove flat borders (letterboxing, screenshot padding)."""
    bg = Image.new(img.mode, img.size, img.getpixel((0, 0)))
    diff = ImageChops.difference(img, bg).convert("L").point(lambda p: 255 if p > tolerance else 0)
    box = diff.getbbox()
    if not box:
        return img
    w, h = box[2] - box[0], box[3] - box[1]
    if w < img.width * 0.3 or h < img.height * 0.3:
        return img  # trimming would remove most of the picture; leave it
    return img.crop(box)


def _bits_ahash(gray8: np.ndarray) -> np.ndarray:
    return (gray8 > gray8.mean()).flatten()


def _bits_dhash(gray9x8: np.ndarray) -> np.ndarray:
    return (gray9x8[:, 1:] > gray9x8[:, :-1]).flatten()


def _bits_phash(gray32: np.ndarray) -> np.ndarray:
    dct = _DCT32 @ gray32 @ _DCT32.T
    low = dct[:8, :8].flatten()
    return low > np.median(low[1:])


def _color_hist(img: Image.Image) -> np.ndarray:
    hsv = np.asarray(img.resize((64, 64)).convert("HSV"), dtype=np.float32)
    h = (hsv[..., 0] / 256 * 12).astype(int)
    s = (hsv[..., 1] / 256 * 4).astype(int)
    v = (hsv[..., 2] / 256 * 4).astype(int)
    hist = np.bincount((h * 16 + s * 4 + v).flatten(), minlength=192).astype(np.float32)
    hist /= hist.sum() or 1
    return hist


@dataclass
class _View:
    ahash: np.ndarray
    dhash: np.ndarray
    phash: np.ndarray
    color: np.ndarray


def _view(img: Image.Image) -> _View:
    gray = ImageOps.autocontrast(img.convert("L"), cutoff=1)  # cancels brightness/contrast edits
    return _View(
        ahash=_bits_ahash(np.asarray(gray.resize((8, 8), Image.LANCZOS), dtype=np.float32)),
        dhash=_bits_dhash(np.asarray(gray.resize((9, 8), Image.LANCZOS), dtype=np.float32)),
        phash=_bits_phash(np.asarray(gray.resize((32, 32), Image.LANCZOS), dtype=np.float32)),
        color=_color_hist(img),
    )


@dataclass
class Fingerprint:
    width: int
    height: int
    views: list[_View] = field(default_factory=list)  # views[0] is the full image

    @property
    def phash_hex(self) -> str:
        bits = self.views[0].phash
        return f"{int(''.join('1' if b else '0' for b in bits), 2):016x}"


def fingerprint(img: Image.Image, crops: bool = True, trim: bool = True) -> Fingerprint:
    """Fingerprint an image. With crops=True also stores crop and mirror views.

    Flat borders are trimmed first so letterboxed / padded copies still match.
    """
    fp = Fingerprint(img.width, img.height)
    if trim:
        img = trim_borders(img)
    windows = _WINDOWS if crops else _WINDOWS[:1]
    for l, t, r, b in windows:
        box = (int(l * img.width), int(t * img.height), int(r * img.width), int(b * img.height))
        fp.views.append(_view(img.crop(box)))
    fp.views.append(_view(ImageOps.mirror(img)))
    return fp


def _hash_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Hamming similarity rescaled so random images score ~0 and identical 1."""
    raw = 1 - np.count_nonzero(a != b) / a.size
    return float(max(0.0, (raw - 0.5) / 0.5))


def _color_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.minimum(a, b).sum())  # histogram intersection, 0..1


def compare_views(a: _View, b: _View) -> dict[str, float]:
    parts = {
        "phash": _hash_sim(a.phash, b.phash),
        "dhash": _hash_sim(a.dhash, b.dhash),
        "ahash": _hash_sim(a.ahash, b.ahash),
        "color": _color_sim(a.color, b.color),
    }
    parts["score"] = sum(WEIGHTS[k] * v for k, v in parts.items())
    return parts


def similarity(query: Fingerprint, cand: Fingerprint) -> dict[str, float]:
    """Best score between any query view and the candidate's full view (and vice versa).

    Checking query-crops against the candidate finds a candidate that is a crop
    of the query; checking candidate-crops against the query finds the reverse.
    """
    best = compare_views(query.views[0], cand.views[0])
    best["transform"] = 0.0  # 0 = direct
    pairs = [(qv, cand.views[0]) for qv in query.views[1:]] + \
            [(query.views[0], cv) for cv in cand.views[1:]]
    for qv, cv in pairs:
        s = compare_views(qv, cv)
        if s["score"] > best["score"]:
            best = s
            best["transform"] = 1.0  # matched via a crop or mirror
    return best


def verdict(score: float) -> str:
    if score >= 0.90:
        return "exact"
    if score >= 0.80:
        return "strong"
    if score >= 0.68:
        return "possible"
    return "weak"
