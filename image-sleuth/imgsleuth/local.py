"""Search a folder on disk for copies of the query image (fully offline)."""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .engines import Match
from .fingerprint import Fingerprint, fingerprint, load_image, similarity, verdict

EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic", ".avif"}


def _scan(path: Path, query: Fingerprint) -> Match | None:
    try:
        img = load_image(str(path))
    except Exception:  # noqa: BLE001 - unreadable files are skipped
        return None
    s = round(similarity(query, fingerprint(img, crops=True))["score"], 4)
    return Match(engine="local", page_url=str(path), image_url=str(path), title=path.name,
                 width=img.width, height=img.height, verified_score=s, verdict=verdict(s),
                 engines=["local"])


def search_folder(folder: str, query: Fingerprint, min_score: float,
                  exclude: Path | None = None) -> list[Match]:
    files = [p for p in Path(folder).rglob("*") if p.suffix.lower() in EXTS and p.is_file()]
    if exclude:
        files = [p for p in files if p.resolve() != exclude.resolve()]
    with ThreadPoolExecutor(os.cpu_count() or 4) as pool:
        results = [m for m in pool.map(lambda p: _scan(p, query), files) if m]
    return sorted((m for m in results if m.verified_score >= min_score),
                  key=lambda m: m.verified_score, reverse=True)
