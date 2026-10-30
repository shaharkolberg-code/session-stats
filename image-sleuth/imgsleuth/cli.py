"""imgsleuth - Sherlock-style reverse image search across many engines."""
from __future__ import annotations

import argparse
import io
import mimetypes
import os
import sys
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from . import __version__, report
from .engines import ENGINES, UA, EngineResult, Query, run_engine
from .fingerprint import fingerprint, load_image, trim_borders
from .local import search_folder
from .verify import fetch_image, merge, verify

BANNER = r"""
  _                       _            _   _
 (_)_ __ ___   __ _   ___| | ___ _   _| |_| |__
 | | '_ ` _ \ / _` | / __| |/ _ \ | | | __| '_ \
 | | | | | | | (_| | \__ \ |  __/ |_| | |_| | | |
 |_|_| |_| |_|\__, | |___/_|\___|\__,_|\__|_| |_|
              |___/   reverse image search  v{}
"""


def upload_temp(data: bytes, filename: str, proxy: str | None) -> str:
    """Upload to litterbox.catbox.moe (auto-deletes after 1h) to get a public URL."""
    r = requests.post("https://litterbox.catbox.moe/resources/internals/api.php",
                      data={"reqtype": "fileupload", "time": "1h"},
                      files={"fileToUpload": (filename, data)}, headers={"User-Agent": UA},
                      proxies={"http": proxy, "https": proxy} if proxy else None, timeout=60)
    r.raise_for_status()
    if not r.text.startswith("https://"):
        raise RuntimeError(r.text[:200])
    return r.text.strip()


def prepare(img, trim: bool) -> tuple[bytes, object]:
    """Return JPEG bytes to send to engines and the (optionally trimmed) image."""
    if trim:
        img = trim_borders(img)
    if max(img.size) > 2400:  # engines reject huge uploads; 2400px loses nothing for matching
        img = img.copy()
        img.thumbnail((2400, 2400))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=93)
    return buf.getvalue(), img


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="imgsleuth", description=__doc__)
    p.add_argument("images", nargs="*", help="image file paths or http(s) URLs")
    p.add_argument("-e", "--engines", help="comma-separated engines to use (default: all)")
    p.add_argument("-x", "--exclude", help="comma-separated engines to skip")
    p.add_argument("-c", "--category", choices=["general", "art", "anime"],
                   help="only use engines in this category")
    p.add_argument("--dir", help="also search this local folder for copies (offline)")
    p.add_argument("--host", action="store_true",
                   help="upload local files to a temporary public host (1h) so URL-only "
                        "engines work too. Your image becomes public for that hour.")
    p.add_argument("--trim", action="store_true", help="strip flat borders before searching")
    p.add_argument("--no-verify", action="store_true",
                   help="skip downloading candidates to check them (faster, less accurate)")
    p.add_argument("--min-score", type=float, default=0.68,
                   help="hide verified matches below this score (0-1, default 0.68)")
    p.add_argument("-n", "--top", type=int, default=25, help="matches to print (default 25)")
    p.add_argument("-t", "--timeout", type=float, default=25, help="per-request timeout seconds")
    p.add_argument("--proxy", default=os.environ.get("IMGSLEUTH_PROXY"),
                   help="HTTP/SOCKS proxy for all requests, e.g. socks5://127.0.0.1:9050")
    p.add_argument("--open", action="store_true", help="open link-only engines in your browser")
    p.add_argument("--json", metavar="FILE", help="write full results as JSON")
    p.add_argument("--csv", metavar="FILE", help="write matches as CSV")
    p.add_argument("--html", metavar="FILE", help="write a visual HTML report")
    p.add_argument("-q", "--quiet", action="store_true", help="no banner")
    p.add_argument("--web", action="store_true", help="open the easy browser app instead")
    p.add_argument("--list-engines", action="store_true", help="list engines and exit")
    p.add_argument("--version", action="version", version=f"imgsleuth {__version__}")
    return p.parse_args(argv)


def pick_engines(args) -> list:
    names = list(ENGINES)
    if args.engines:
        names = [n.strip() for n in args.engines.split(",")]
        bad = [n for n in names if n not in ENGINES]
        if bad:
            sys.exit(f"unknown engine(s): {', '.join(bad)}. See --list-engines")
    if args.exclude:
        drop = {n.strip() for n in args.exclude.split(",")}
        names = [n for n in names if n not in drop]
    if args.category:
        names = [n for n in names if ENGINES[n].category == args.category]
    return [ENGINES[n] for n in names]


def search_one(target: str, args, engines) -> dict:
    is_url = target.startswith(("http://", "https://"))
    if is_url:
        raw = fetch_image(target, args.timeout, args.proxy)
        if raw is None:
            raise SystemExit(f"could not download {target}")
        filename = Path(target.split("?")[0]).name or "image.jpg"
    else:
        raw = Path(target).read_bytes()
        filename = Path(target).name
    original = load_image(raw)
    data, img = prepare(original, args.trim)
    qfp = fingerprint(img)
    print(report._c("1", f"\n[*] {target}") + f"  {original.width}x{original.height}  pHash {qfp.phash_hex}")

    public_url = target if is_url and not args.trim else None
    if args.host and not public_url and engines:
        try:
            public_url = upload_temp(data, filename, args.proxy)
            print(f"[*] temporary public URL (1h): {public_url}")
        except Exception as ex:  # noqa: BLE001
            print(report.ICON["error"] + f" temp upload failed: {ex}")

    q = Query(data=data, filename=Path(filename).stem + ".jpg", url=public_url,
              mime=mimetypes.types_map[".jpg"])
    results: list[EngineResult] = []
    if engines:
        with ThreadPoolExecutor(len(engines)) as pool:
            futs = [pool.submit(run_engine, e, q, args.timeout, args.proxy) for e in engines]
            for f in as_completed(futs):
                r = f.result()
                results.append(r)
                report.print_engine(r)
        results.sort(key=lambda r: list(ENGINES).index(r.engine))

    found = [m for r in results for m in r.matches]
    if found and not args.no_verify:
        print(f"[*] verifying {len(found)} candidate(s)...")
        verify(found, qfp, timeout=min(args.timeout, 15), proxy=args.proxy)
    matches = merge(found)
    matches = [m for m in matches if m.verified_score is None or m.verified_score >= args.min_score]

    if args.dir:
        local = search_folder(args.dir, qfp, args.min_score,
                              exclude=None if is_url else Path(target))
        print(f"{report.ICON['found' if local else 'not_found']} {'local':<12} "
              f"{len(local)} match(es) in {args.dir}")
        matches = local + matches

    report.print_matches(matches, args.top)
    if args.open:
        for r in results:
            if r.status == "link" and r.search_url:
                webbrowser.open_new_tab(r.search_url)
    return report.to_dict(target, qfp.phash_hex, results, matches)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.list_engines:
        for e in ENGINES.values():
            print(f"{e.name:<12} {e.category:<8} {e.homepage:<30} {e.needs}")
        return 0
    if args.web:
        from .web import serve
        serve(base_args=args)
        return 0
    if not args.images:
        print("usage: imgsleuth IMAGE [IMAGE ...]  (see --help)")
        return 2
    if not args.quiet:
        print(BANNER.format(__version__))
    engines = pick_engines(args)
    reports = [search_one(t, args, engines) for t in args.images]
    for flag, writer in ((args.json, report.write_json), (args.csv, report.write_csv),
                         (args.html, report.write_html)):
        if flag:
            writer(flag, reports)
            print(f"[*] saved {flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
