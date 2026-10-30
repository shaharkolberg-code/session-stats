"""Simple web app: pick a photo in the browser, get the results page.

Run `imgsleuth-app` (or `imgsleuth --web`). Uses only the standard library.
"""
from __future__ import annotations

import io
import json
import tempfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import __version__

MAX_UPLOAD = 25 * 1024 * 1024
_lock = threading.Lock()  # one search at a time keeps engines from rate-limiting us

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Image Sleuth</title><style>
:root{--bg:#f6f6f8;--fg:#18181b;--mute:#6b6b74;--card:#fff;--line:#e3e3e8;--accent:#2f5bea;--ok:#178a3e;--mid:#a86e00;--bad:#c4302b}
@media (prefers-color-scheme:dark){:root{--bg:#121214;--fg:#ececf0;--mute:#9a9aa3;--card:#1c1c20;--line:#2c2c32;--accent:#7c9cff;--ok:#4cd07d;--mid:#e0b040;--bad:#ff6b63}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,sans-serif}
main{max-width:980px;margin:0 auto;padding:20px 16px 60px}h1{font-size:26px;margin:4px 0}p.sub{color:var(--mute);margin:0 0 18px}
#drop{display:block;border:2px dashed var(--line);border-radius:14px;background:var(--card);padding:28px 16px;text-align:center;cursor:pointer}
#drop.over{border-color:var(--accent)}#drop img{max-width:100%;max-height:260px;border-radius:8px;display:block;margin:0 auto 10px}
.row{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:14px 0}
input[type=url]{flex:1;min-width:0;padding:11px 12px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:inherit;font:inherit}
button{padding:12px 22px;border:0;border-radius:10px;background:var(--accent);color:#fff;font:600 16px system-ui;cursor:pointer}
button:disabled{opacity:.5;cursor:default}label.opt{color:var(--mute);font-size:14px}
.engines{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:8px;margin:18px 0}
.eng{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;font-size:14px}
.eng b{display:block}.eng a{color:var(--accent)}.found{color:var(--ok)}.error{color:var(--bad)}.mute{color:var(--mute)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;word-break:break-word;font-size:14px}
.card img{width:100%;height:180px;object-fit:contain;display:block;background:var(--line)}.card div{padding:8px 10px}
.v-exact,.v-strong{color:var(--ok);font-weight:700}.v-possible{color:var(--mid);font-weight:700}
.spin{display:inline-block;width:18px;height:18px;border:3px solid var(--line);border-top-color:var(--accent);border-radius:50%;animation:s 1s linear infinite;vertical-align:-4px;margin-right:8px}
@keyframes s{to{transform:rotate(360deg)}}.empty{background:var(--card);border-radius:12px;padding:18px;text-align:center}
</style></head><body><main>
<h1>Image Sleuth</h1><p class="sub">Find where a picture appears online. Every result is downloaded and checked against your image.</p>
<label id="drop"><input id="file" type="file" accept="image/*" hidden><span id="dropText"><b>Tap to choose a photo</b><br><span class="mute">or drag one here</span></span></label>
<div class="row"><input id="url" type="url" placeholder="…or paste an image link"><button id="go" disabled>Search</button></div>
<div class="row"><label class="opt"><input id="trim" type="checkbox"> Remove borders (screenshots)</label></div>
<div id="status"></div><div id="engines" class="engines"></div><div id="results"></div>
</main><script>
const $=id=>document.getElementById(id), esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let file=null;
function pick(f){if(!f)return;file=f;$("url").value="";const u=URL.createObjectURL(f);$("dropText").innerHTML=`<img src="${u}" alt=""><span class="mute">${esc(f.name)} · tap to change</span>`;$("go").disabled=false}
$("file").onchange=e=>pick(e.target.files[0]);
const d=$("drop");d.ondragover=e=>{e.preventDefault();d.classList.add("over")};d.ondragleave=()=>d.classList.remove("over");
d.ondrop=e=>{e.preventDefault();d.classList.remove("over");pick(e.dataTransfer.files[0])};
$("url").oninput=()=>{$("go").disabled=!($("url").value.trim()||file)};
$("go").onclick=async()=>{
  const url=$("url").value.trim(), q=new URLSearchParams({trim:$("trim").checked?1:0});
  if(url)q.set("url",url);
  $("go").disabled=true;$("engines").innerHTML="";$("results").innerHTML="";
  $("status").innerHTML='<p><span class="spin"></span>Searching 9 engines and checking every result… this takes up to a minute.</p>';
  try{
    const r=await fetch("/search?"+q,{method:"POST",body:url?null:file});
    const data=await r.json(); if(!r.ok)throw new Error(data.error||r.status); show(data);
  }catch(e){$("status").innerHTML=`<p class="error">Search failed: ${esc(e.message)}</p>`}
  $("go").disabled=false};
function show(d){
  const n=d.matches.length;
  $("status").innerHTML=`<h2>${n?n+" match"+(n>1?"es":"")+" found":"No copies found online"}</h2>`;
  const label={found:"found",not_found:"no matches",link:"open to check",error:"failed",skipped:"skipped"};
  $("engines").innerHTML=d.engines.map(e=>`<div class="eng"><b>${esc(e.engine)}</b><span class="${e.status}">${label[e.status]}${e.count?" ("+e.count+")":""}</span>
    ${e.search_url&&e.status!=="found"?` · <a href="${esc(e.search_url)}" target="_blank" rel="noopener">open</a>`:""}${e.error&&e.status!=="link"?`<div class="mute">${esc(e.error)}</div>`:""}</div>`).join("");
  $("results").innerHTML=n?`<div class="grid">${d.matches.map(m=>{const href=m.page_url||m.image_url,img=m.thumb_url||m.image_url,v=m.verdict||"unverified";
    return `<a class="card" href="${esc(href)}" target="_blank" rel="noopener" style="color:inherit;text-decoration:none">${img?`<img loading="lazy" src="/thumb?u=${encodeURIComponent(img)}" alt="" onerror="this.remove()">`:""}
    <div><span class="v-${v}">${Math.round(m.confidence*100)}% ${v}</span> <span class="mute">· ${esc(m.engines.join(", "))}</span><br>${esc(m.title.slice(0,80))}<br><span class="mute">${esc(new URL(href).hostname)}</span></div></a>`}).join("")}</div>`
    :`<p class="empty mute">None of the engines returned a copy of this image. Engines marked "open to check" can only be checked in your browser.</p>`}
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = f"imgsleuth/{__version__}"

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj).encode(), "application/json")

    def do_GET(self):
        parts = urlsplit(self.path)
        if parts.path in ("/", "/index.html"):
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        elif parts.path == "/thumb":
            self._thumb(parse_qs(parts.query).get("u", [""])[0])
        else:
            self._json(404, {"error": "not found"})

    def _thumb(self, url: str) -> None:
        """Fetch a result thumbnail server-side (many sites block hotlinking) and
        re-encode it as a small JPEG, so only real images are ever served."""
        from .fingerprint import load_image
        from .verify import fetch_image
        data = fetch_image(url, 15) if url.startswith(("http://", "https://")) else None
        try:
            img = load_image(data)
            img.thumbnail((400, 400))
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=82)
        except Exception:  # noqa: BLE001 - missing or undecodable thumbnail
            return self._send(404, b"", "text/plain")
        self._send(200, buf.getvalue(), "image/jpeg")

    def do_POST(self):
        parts = urlsplit(self.path)
        if parts.path != "/search":
            return self._json(404, {"error": "not found"})
        qs = {k: v[0] for k, v in parse_qs(parts.query).items()}
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_UPLOAD:
            return self._json(413, {"error": "image is larger than 25 MB"})
        body = self.rfile.read(length) if length else b""
        target = qs.get("url", "").strip()
        if not target and not body:
            return self._json(400, {"error": "choose an image or paste a link"})
        if target and not target.startswith(("http://", "https://")):
            return self._json(400, {"error": "link must start with http:// or https://"})
        try:
            with _lock, tempfile.TemporaryDirectory() as tmp:
                if not target:
                    target = str(Path(tmp) / "upload.jpg")
                    Path(target).write_bytes(body)
                result = self.server.search(target, qs.get("trim") == "1")
        except SystemExit as e:  # search_one exits on undownloadable URLs
            return self._json(400, {"error": str(e)})
        except Exception as e:  # noqa: BLE001 - report any failure to the page
            return self._json(500, {"error": f"{type(e).__name__}: {e}"})
        result["query"] = qs.get("url") or "uploaded image"
        self._json(200, result)

    def log_message(self, fmt, *args):  # keep the console for search output
        pass


def serve(port: int = 8765, host: str = "127.0.0.1", open_browser: bool = True, base_args=None) -> None:
    from .cli import parse_args, pick_engines, search_one

    defaults = base_args or parse_args(["-q"])

    def search(target: str, trim: bool) -> dict:
        args = parse_args(["-q"])
        for k in ("timeout", "proxy", "min_score", "engines", "exclude", "category"):
            setattr(args, k, getattr(defaults, k))
        args.trim = trim
        args.top = 0
        return search_one(target, args, pick_engines(args))

    server = ThreadingHTTPServer((host, port), Handler)
    server.search = search
    url = f"http://{'localhost' if host in ('127.0.0.1', '0.0.0.0') else host}:{port}/"
    print(f"Image Sleuth is running at {url}  (press Ctrl+C to stop)")
    if host == "0.0.0.0":
        print("Also reachable from other devices on your Wi-Fi at this computer's IP address.")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(prog="imgsleuth-app", description="Image Sleuth web app")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--lan", action="store_true", help="let phones on your Wi-Fi use it too")
    p.add_argument("--no-browser", action="store_true")
    a = p.parse_args()
    serve(a.port, "0.0.0.0" if a.lan else "127.0.0.1", not a.no_browser)

