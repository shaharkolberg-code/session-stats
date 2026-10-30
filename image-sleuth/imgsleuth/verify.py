"""Download each candidate, fingerprint it, and score it against the query."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import requests

from .engines import UA, Match
from .social import platform
from .fingerprint import Fingerprint, fingerprint, load_image, similarity, verdict

MAX_BYTES = 15 * 1024 * 1024


def fetch_image(url: str, timeout: float, proxy: str | None = None) -> bytes | None:
    if not url.startswith(("http://", "https://")):
        return None
    try:
        with requests.get(url, timeout=timeout, stream=True, headers={"User-Agent": UA},
                          proxies={"http": proxy, "https": proxy} if proxy else None) as r:
            if r.status_code != 200:
                return None
            buf = bytearray()
            for chunk in r.iter_content(64 * 1024):
                buf += chunk
                if len(buf) > MAX_BYTES:
                    return None
            return bytes(buf)
    except requests.RequestException:
        return None


def _score_one(m: Match, query: Fingerprint, timeout: float, proxy: str | None) -> None:
    for url in (m.image_url, m.thumb_url):
        data = fetch_image(url, timeout, proxy) if url else None
        if not data:
            continue
        try:
            img = load_image(data)
        except Exception:  # noqa: BLE001 - any undecodable file just isn't verifiable
            continue
        m.verified_score = round(similarity(query, fingerprint(img, crops=False))["score"], 4)
        m.verdict = verdict(m.verified_score)
        if not m.width:
            m.width, m.height = img.size
        return


def verify(matches: list[Match], query: Fingerprint, timeout: float = 15,
           proxy: str | None = None, workers: int = 12) -> None:
    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(lambda m: _score_one(m, query, timeout, proxy), matches))


def _key(m: Match) -> str:
    u = urlsplit(m.page_url or m.image_url)
    social = platform(m.page_url)
    if social:  # same post on pinterest.com / de.pinterest.com / pinterest.se is one result
        return social + u.path.rstrip("/").lower()
    return (u.netloc.lower().removeprefix("www.") + u.path.rstrip("/")).lower()


def confidence(m: Match) -> float:
    """Single ranking number: verified score first, engine score as fallback,
    with a small bonus when several engines independently found the same page."""
    base = m.verified_score if m.verified_score is not None else (m.engine_score or 0) * 0.9
    return min(1.0, base + 0.03 * (len(m.engines) - 1))


def merge(matches: list[Match]) -> list[Match]:
    """Collapse the same page found by several engines into one entry."""
    merged: dict[str, Match] = {}
    for m in matches:
        k = _key(m) or id(m)
        cur = merged.get(k)
        if cur is None:
            m.engines = [m.engine]
            merged[k] = m
            continue
        if m.engine not in cur.engines:
            cur.engines.append(m.engine)
        if (m.verified_score or -1) > (cur.verified_score or -1):
            for f in ("verified_score", "verdict", "image_url", "thumb_url", "width", "height"):
                setattr(cur, f, getattr(m, f))
        cur.title = cur.title or m.title
    for m in merged.values():
        m.platform = platform(m.page_url) or platform(m.image_url)
    return sorted(merged.values(), key=confidence, reverse=True)
