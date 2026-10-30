"""Console, JSON, CSV and HTML output."""
from __future__ import annotations

import csv
import html
import json
import sys
from dataclasses import asdict

from .engines import EngineResult, Match
from .verify import confidence

_TTY = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _TTY else text


ICON = {"found": _c("32", "[+]"), "not_found": _c("90", "[-]"), "link": _c("36", "[>]"),
        "error": _c("31", "[!]"), "skipped": _c("90", "[ ]")}
VERDICT_COLOR = {"exact": "1;32", "strong": "32", "possible": "33", "weak": "90", "": "37"}


def print_engine(r: EngineResult) -> None:
    detail = {
        "found": f"{len(r.matches)} match(es)",
        "not_found": "no matches",
        "link": "open: " + r.search_url,
        "error": r.error,
        "skipped": r.error,
    }[r.status]
    if r.status == "link" and r.error:
        detail += f"  ({r.error})"
    print(f"{ICON[r.status]} {r.engine:<12} {detail}")


def print_matches(matches: list[Match], limit: int) -> None:
    if not matches:
        print(_c("90", "\nNo matches above the score threshold."))
        return
    print(_c("1", f"\nTop matches ({min(limit, len(matches))} of {len(matches)}):"))
    for i, m in enumerate(matches[:limit], 1):
        conf = confidence(m)
        tag = m.verdict or "unverified"
        label = _c(VERDICT_COLOR.get(m.verdict, "37"), f"{conf:5.0%} {tag:<10}")
        size = f"{m.width}x{m.height}" if m.width else ""
        print(f"{i:>3}. {label} {', '.join(m.engines):<18} {size:>10}  {m.page_url or m.image_url}")
        if m.title:
            print(f"     {_c('90', m.title[:100])}")


def to_dict(path: str, fp_hex: str, results: list[EngineResult], matches: list[Match]) -> dict:
    return {
        "query": path, "phash": fp_hex,
        "engines": [{k: v for k, v in asdict(r).items() if k != "matches"} | {"count": len(r.matches)}
                    for r in results],
        "matches": [asdict(m) | {"confidence": round(confidence(m), 4)} for m in matches],
    }


def write_json(path: str, reports: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(reports if len(reports) > 1 else reports[0], f, indent=2)


def write_csv(path: str, reports: list[dict]) -> None:
    cols = ["query", "confidence", "verdict", "verified_score", "engine_score", "engines",
            "page_url", "image_url", "title", "width", "height"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, cols, extrasaction="ignore")
        w.writeheader()
        for rep in reports:
            for m in rep["matches"]:
                w.writerow(m | {"query": rep["query"], "engines": "+".join(m["engines"])})


def write_html(path: str, reports: list[dict]) -> None:
    e = html.escape
    parts = ["""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Image Sleuth Report</title><style>
:root{--bg:#fff;--fg:#1a1a1a;--mute:#666;--card:#f4f4f6;--ok:#178a3e;--mid:#b07800}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--fg:#eee;--mute:#999;--card:#222226;--ok:#4cd07d;--mid:#e0b040}}
body{background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,sans-serif;margin:0 auto;max-width:960px;padding:16px}
a{color:inherit}.mute{color:var(--mute)}.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(200px,1fr))}
.card{background:var(--card);border-radius:10px;padding:10px;overflow:hidden;word-break:break-all}
.card img{width:100%;height:150px;object-fit:contain;background:#0001;border-radius:6px}
.exact,.strong{color:var(--ok);font-weight:600}.possible{color:var(--mid);font-weight:600}
ul.eng{list-style:none;padding:0;columns:2}</style><h1>Image Sleuth Report</h1>"""]
    for rep in reports:
        parts.append(f"<h2>{e(rep['query'])}</h2><p class=mute>pHash {e(rep['phash'])}</p><ul class=eng>")
        for r in rep["engines"]:
            link = f' — <a href="{e(r["search_url"])}" target=_blank>open</a>' if r["search_url"] else ""
            parts.append(f"<li><b>{e(r['engine'])}</b> {e(r['status'])} "
                         f"{r['count'] or ''}{link} <span class=mute>{e(r['error'])}</span></li>")
        parts.append("</ul><div class=grid>")
        for m in rep["matches"]:
            thumb = m["thumb_url"] or m["image_url"]
            href = m["page_url"] or m["image_url"]
            v = m["verdict"] or "unverified"
            parts.append(
                f'<div class=card><a href="{e(href)}" target=_blank>'
                + (f'<img loading=lazy src="{e(thumb)}" alt="">' if thumb else "")
                + f'</a><div class="{e(v)}">{m["confidence"]:.0%} {e(v)}</div>'
                f'<div class=mute>{e("+".join(m["engines"]))}</div>'
                f'<div>{e(m["title"][:80])}</div><a class=mute href="{e(href)}" target=_blank>'
                f'{e(href[:90])}</a></div>')
        parts.append("</div>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(parts))
