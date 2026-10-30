"""Reverse image search engines.

Like Sherlock's site list, every engine is one entry in ENGINES. Each engine
gets the query (image bytes and/or a public URL) and returns an EngineResult:
  found     - the engine returned parsed matches
  not_found - the engine answered and had nothing
  link      - results can't be scraped; `search_url` opens them in a browser
  error     - request failed / blocked / layout changed
  skipped   - engine can't run with this input (e.g. needs a URL or API key)
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


@dataclass
class Match:
    engine: str
    page_url: str = ""          # page where the image appears
    image_url: str = ""         # full-size image, if known
    thumb_url: str = ""         # thumbnail, used for verification if no full image
    title: str = ""
    width: int = 0
    height: int = 0
    engine_score: float | None = None   # engine's own similarity, 0..1
    verified_score: float | None = None  # our fingerprint score, 0..1
    verdict: str = ""
    engines: list[str] = field(default_factory=list)  # all engines that found it
    platform: str = ""          # social media platform, if the page is on one


@dataclass
class EngineResult:
    engine: str
    status: str
    search_url: str = ""
    matches: list[Match] = field(default_factory=list)
    error: str = ""


@dataclass
class Query:
    data: bytes | None
    filename: str
    url: str | None             # public URL of the image, if available
    mime: str = "image/jpeg"


@dataclass
class Engine:
    name: str
    homepage: str
    category: str               # general | art | anime
    run: Callable[[Query, requests.Session, float], EngineResult]
    needs: str = ""             # human note shown in --list-engines


def _session(proxy: str | None = None) -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    if proxy:
        s.proxies.update({"http": proxy, "https": proxy})
    return s


def strip_tracking(url: str) -> str:
    """Drop utm_* tags so links are clean and the same page merges across engines."""
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not k.startswith("utm_")]
    return urlunsplit(parts._replace(query=urlencode(query)))


def _abs(url: str, base: str) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    return urljoin(base, url)


# --------------------------------------------------------------------------- TinEye
def parse_tineye(payload: dict) -> list[Match]:
    out = []
    for m in payload.get("matches", []):
        links = m.get("backlinks") or []
        page = links[0].get("backlink", "") if links else ""
        img = links[0].get("url", "") if links else m.get("image_url", "")
        out.append(Match(
            engine="tineye", page_url=page, image_url=img,
            thumb_url=m.get("image_url", ""), title=m.get("domain", ""),
            width=m.get("width") or 0, height=m.get("height") or 0,
            engine_score=(m["score"] / 100) if isinstance(m.get("score"), (int, float)) else None,
        ))
    return out


def tineye(q: Query, s: requests.Session, timeout: float) -> EngineResult:
    try:
        return _tineye(q, s, timeout)
    except (requests.RequestException, ValueError):
        # TinEye's API often refuses automated clients; fall back to its web page.
        if q.url:
            return EngineResult("tineye", "link", f"https://tineye.com/search?url={quote(q.url, safe='')}",
                                error="API unavailable - open the link")
        raise


def _tineye(q: Query, s: requests.Session, timeout: float) -> EngineResult:
    api = "https://tineye.com/api/v1/result_json/?sort=score&order=desc"
    if q.data:
        r = s.post(api, files={"image": (q.filename, q.data, q.mime)}, timeout=timeout)
    else:
        r = s.post(api, data={"url": q.url}, timeout=timeout)
    r.raise_for_status()
    payload = r.json()
    link = f"https://tineye.com/search/{payload['query_hash']}" if payload.get("query_hash") else \
        (f"https://tineye.com/search?url={quote(q.url, safe='')}" if q.url else "")
    matches = parse_tineye(payload)
    return EngineResult("tineye", "found" if matches else "not_found", link, matches)


# --------------------------------------------------------------------------- trace.moe
def parse_tracemoe(payload: dict) -> list[Match]:
    out = []
    for r in payload.get("result", []):
        al = r.get("anilist")
        title, al_id = "", al
        if isinstance(al, dict):
            al_id = al.get("id")
            t = al.get("title") or {}
            title = t.get("english") or t.get("romaji") or t.get("native") or ""
        ep = r.get("episode")
        mins = int((r.get("from") or 0) // 60)
        secs = int((r.get("from") or 0) % 60)
        title = f"{title or r.get('filename', '')} ep {ep} @ {mins}:{secs:02d}".strip()
        out.append(Match(
            engine="tracemoe", page_url=f"https://anilist.co/anime/{al_id}" if al_id else "",
            thumb_url=r.get("image", ""), title=title,
            engine_score=r.get("similarity"),
        ))
    return out


def tracemoe(q: Query, s: requests.Session, timeout: float) -> EngineResult:
    api = "https://api.trace.moe/search?anilistInfo&cutBorders"
    if q.data:
        r = s.post(api, files={"image": (q.filename, q.data, q.mime)}, timeout=timeout)
    else:
        r = s.get(api + "&url=" + quote(q.url, safe=""), timeout=timeout)
    r.raise_for_status()
    payload = r.json()
    if payload.get("error"):
        return EngineResult("tracemoe", "error", error=payload["error"])
    # trace.moe always returns its closest guesses; under ~87% they are noise.
    matches = [m for m in parse_tracemoe(payload) if (m.engine_score or 0) >= 0.87]
    link = f"https://trace.moe/?url={quote(q.url, safe='')}" if q.url else "https://trace.moe/"
    return EngineResult("tracemoe", "found" if matches else "not_found", link, matches)


# --------------------------------------------------------------------------- IQDB
def parse_iqdb(html: str, base: str = "https://iqdb.org/") -> list[Match]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    pages = soup.find(id="pages") or soup
    for table in pages.find_all("table"):
        th = table.find("th")
        head = th.get_text(strip=True) if th else ""
        if head.lower().startswith(("your image", "no relevant")):
            continue
        a = table.find("a", href=True)
        img = table.find("img")
        sim_td = next((td for td in table.find_all("td") if "similarity" in td.get_text()), None)
        if not a or not sim_td:
            continue
        sim = re.search(r"(\d+(?:\.\d+)?)%", sim_td.get_text())
        size = re.search(r"(\d+)\s*[×x]\s*(\d+)", table.get_text())
        out.append(Match(
            engine="iqdb", page_url=_abs(a["href"], base),
            thumb_url=_abs(img.get("src", ""), base) if img else "",
            title=(img.get("alt", "") if img else "")[:120],
            width=int(size.group(1)) if size else 0, height=int(size.group(2)) if size else 0,
            engine_score=float(sim.group(1)) / 100 if sim else None,
        ))
    return out


def iqdb(q: Query, s: requests.Session, timeout: float) -> EngineResult:
    base = "https://iqdb.org/"
    if q.data:
        r = s.post(base, files={"file": (q.filename, q.data, q.mime)}, timeout=timeout)
    else:
        r = s.get(base + "?url=" + quote(q.url, safe=""), timeout=timeout)
    r.raise_for_status()
    matches = [m for m in parse_iqdb(r.text) if (m.engine_score or 0) >= 0.80]
    link = base + "?url=" + quote(q.url, safe="") if q.url else ""
    return EngineResult("iqdb", "found" if matches else "not_found", link, matches)


# --------------------------------------------------------------------------- SauceNAO
def parse_saucenao(payload: dict) -> list[Match]:
    out = []
    for r in payload.get("results", []):
        h, d = r.get("header", {}), r.get("data", {})
        urls = d.get("ext_urls") or []
        title = d.get("title") or d.get("source") or d.get("material") or h.get("index_name", "")
        try:
            sim = float(h.get("similarity", 0)) / 100
        except ValueError:
            sim = None
        out.append(Match(engine="saucenao", page_url=urls[0] if urls else d.get("source", ""),
                         thumb_url=h.get("thumbnail", ""), title=str(title)[:120],
                         engine_score=sim))
    return out


def saucenao(q: Query, s: requests.Session, timeout: float) -> EngineResult:
    key = os.environ.get("SAUCENAO_API_KEY")
    link = f"https://saucenao.com/search.php?url={quote(q.url, safe='')}" if q.url else ""
    if not key:
        return EngineResult("saucenao", "link" if link else "skipped", link,
                            error="" if link else "set SAUCENAO_API_KEY to search uploads")
    api = f"https://saucenao.com/search.php?output_type=2&numres=16&db=999&api_key={key}"
    if q.data:
        r = s.post(api, files={"file": (q.filename, q.data, q.mime)}, timeout=timeout)
    else:
        r = s.get(api + "&url=" + quote(q.url, safe=""), timeout=timeout)
    r.raise_for_status()
    matches = [m for m in parse_saucenao(r.json()) if (m.engine_score or 0) >= 0.70]
    return EngineResult("saucenao", "found" if matches else "not_found", link, matches)


# --------------------------------------------------------------------------- Yandex
def _find_sites(obj) -> list[dict]:
    """Walk Yandex's embedded JSON state and collect any 'sites' lists."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "sites" and isinstance(v, list):
                found.extend(x for x in v if isinstance(x, dict))
            else:
                found.extend(_find_sites(v))
    elif isinstance(obj, list):
        for v in obj:
            found.extend(_find_sites(v))
    return found


def parse_yandex(html: str) -> list[Match]:
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    for el in soup.find_all(attrs={"data-state": True}):
        try:
            state = json.loads(el["data-state"])
        except (ValueError, TypeError):
            continue
        for site in _find_sites(state):
            page = strip_tracking(site.get("url", ""))
            if not page or page in seen:
                continue
            seen.add(page)
            orig = site.get("originalImage") or {}
            thumb = site.get("thumb") or {}
            out.append(Match(
                engine="yandex", page_url=page, image_url=orig.get("url", ""),
                thumb_url=_abs(thumb.get("url", ""), "https://yandex.com/"),
                title=site.get("title", "")[:120],
                width=orig.get("width") or 0, height=orig.get("height") or 0,
            ))
    return out


def yandex(q: Query, s: requests.Session, timeout: float) -> EngineResult:
    base = "https://yandex.com/images/search"
    if q.data:
        r = s.post(base, params={
            "rpt": "imageview", "format": "json",
            "request": '{"blocks":[{"block":"b-page_type_search-by-image__link"}]}',
        }, files={"upfile": (q.filename, q.data, q.mime)}, timeout=timeout)
        r.raise_for_status()
        params = r.json()["blocks"][0]["params"]
        if params.get("url"):            # older response format
            link = base + "?" + params["url"]
        else:                            # current format: only a cbir id
            link = f"{base}?rpt=imageview&cbir_id={quote(params['cbirId'], safe='')}"
    else:
        link = f"{base}?rpt=imageview&url={quote(q.url, safe='')}"
    page = s.get(link + "&cbir_page=sites", timeout=timeout)
    page.raise_for_status()
    if "captcha" in page.url or "showcaptcha" in page.text[:5000]:
        return EngineResult("yandex", "link", link, error="captcha - open the link")
    matches = parse_yandex(page.text)
    return EngineResult("yandex", "found" if matches else "link", link, matches)


# --------------------------------------------------------------------------- Link engines
def google_lens(q: Query, s: requests.Session, timeout: float) -> EngineResult:
    if q.url:
        return EngineResult("google_lens", "link",
                            "https://lens.google.com/uploadbyurl?url=" + quote(q.url, safe=""))
    r = s.post("https://lens.google.com/v3/upload?hl=en",
               files={"encoded_image": (q.filename, q.data, q.mime)},
               allow_redirects=False, timeout=timeout)
    loc = r.headers.get("Location")
    if not loc:
        m = re.search(r'URL=([^"\']+)', r.text)
        loc = m.group(1).replace("&amp;", "&") if m else ""
    if not loc:
        return EngineResult("google_lens", "error", error=f"no redirect (HTTP {r.status_code})")
    return EngineResult("google_lens", "link", _abs(loc, "https://lens.google.com/"))


def baidu(q: Query, s: requests.Session, timeout: float) -> EngineResult:
    if q.data:
        r = s.post("https://graph.baidu.com/upload?from=pc",
                   files={"image": (q.filename, q.data, q.mime)}, timeout=timeout)
    else:
        r = s.post("https://graph.baidu.com/upload?from=pc", data={"image": q.url}, timeout=timeout)
    r.raise_for_status()
    url = (r.json().get("data") or {}).get("url")
    if not url:
        return EngineResult("baidu", "link", "https://graph.baidu.com/pcpage/index?tpl_from=pc",
                            error="upload refused - open the site and drop the image in")
    return EngineResult("baidu", "link", url)


def _url_only(name: str, template: str):
    def run(q: Query, s: requests.Session, timeout: float) -> EngineResult:
        if not q.url:
            return EngineResult(name, "skipped", error="needs a public URL (use --host)")
        return EngineResult(name, "link", template.format(quote(q.url, safe="")))
    return run


ENGINES: dict[str, Engine] = {e.name: e for e in [
    Engine("tineye", "https://tineye.com", "general", tineye),
    Engine("yandex", "https://yandex.com/images", "general", yandex),
    Engine("google_lens", "https://lens.google.com", "general", google_lens, "opens in browser"),
    Engine("bing", "https://bing.com/visualsearch", "general",
           _url_only("bing", "https://www.bing.com/images/search?view=detailv2&iss=sbi&q=imgurl:{}"),
           "URL input, opens in browser"),
    Engine("baidu", "https://graph.baidu.com", "general", baidu, "opens in browser"),
    Engine("saucenao", "https://saucenao.com", "art", saucenao, "SAUCENAO_API_KEY for parsed results"),
    Engine("iqdb", "https://iqdb.org", "art", iqdb),
    Engine("ascii2d", "https://ascii2d.net", "art",
           _url_only("ascii2d", "https://ascii2d.net/search/url/{}"), "URL input, opens in browser"),
    Engine("tracemoe", "https://trace.moe", "anime", tracemoe),
]}


def run_engine(engine: Engine, q: Query, timeout: float, proxy: str | None) -> EngineResult:
    try:
        return engine.run(q, _session(proxy), timeout)
    except requests.HTTPError as e:
        return EngineResult(engine.name, "error", error=f"HTTP {e.response.status_code}")
    except requests.RequestException as e:
        return EngineResult(engine.name, "error", error=type(e).__name__)
    except (ValueError, KeyError, IndexError, TypeError) as e:
        return EngineResult(engine.name, "error", error=f"unexpected response ({type(e).__name__})")
