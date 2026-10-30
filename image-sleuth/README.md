# imgsleuth

Sherlock-style reverse image search. Give it an image (file or URL) and it
queries many reverse-image engines at once, downloads every candidate they
return, and **verifies each one against your image** with perceptual
fingerprints, so you get a ranked list of real matches instead of a pile of
"visually similar" noise.

```
$ imgsleuth photo.jpg
[*] photo.jpg  1600x1200  pHash b3d7bcb227c041d8
[+] tineye       4 match(es)
[+] yandex       11 match(es)
[>] google_lens  open: https://lens.google.com/search?...
[-] iqdb         no matches
...
Top matches (6 of 6):
  1.  100% exact      tineye, yandex        1600x1200  https://example.com/post/123
  2.   93% exact      yandex                 800x600   https://blog.example.org/a
```

`[+]` found · `[-]` nothing · `[>]` open link in browser · `[!]` error · `[ ]` skipped

## Easiest way: the app

Works on a Mac, Windows or Linux computer (not on a phone directly; see the end of this section).

1. Install Python 3.10+ from [python.org/downloads](https://www.python.org/downloads/).
   On Windows, tick **"Add python.exe to PATH"** on the first installer screen.
2. On GitHub, pick this branch, then **Code → Download ZIP**, and unzip it.
3. Open the `image-sleuth` folder and double-click the starter for your computer:
   - **Windows:** `Start Image Sleuth (Windows).bat`. If a blue "Windows protected your PC" box appears, click **More info → Run anyway**.
   - **Mac:** `Start Image Sleuth (Mac).command`. If macOS says it can't be opened, right-click it → **Open** → **Open**.
     On newer macOS: System Settings → Privacy & Security → scroll down → **Open Anyway**.
   - **Linux:** run `./"Start Image Sleuth (Linux).sh"` in a terminal.
4. A window opens. The first time it sets things up (about a minute, needs internet), then your browser opens the app.
   Keep that window open while you use it.

If the browser doesn't open by itself, go to **http://localhost:8765** yourself.
If something fails, the window stays open and shows the reason.

If double-clicking still doesn't work, open Terminal (Mac) or PowerShell (Windows) in the `image-sleuth` folder and run:

- Mac/Linux: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python -m imgsleuth --web`
- Windows: `py -m venv .venv; .venv\Scripts\pip install -r requirements.txt; .venv\Scripts\python -m imgsleuth --web`

**From your phone:** start it on your computer with `.venv/bin/python -m imgsleuth.web --lan`, then open
`http://<your computer's IP>:8765` on a phone connected to the same Wi-Fi.

## Install (command line)

```bash
cd image-sleuth
pip install .
imgsleuth --list-engines
```

## Engines

| engine | type | results |
|---|---|---|
| tineye | general | parsed + verified |
| yandex | general | parsed + verified (link if captcha) |
| google_lens | general | link |
| bing | general | link (needs URL) |
| baidu | general | link |
| saucenao | art | parsed with `SAUCENAO_API_KEY` (free key), else link |
| iqdb | art / anime | parsed + verified |
| ascii2d | art | link (needs URL) |
| tracemoe | anime screenshots | parsed (episode + timestamp) |

Adding an engine = one function + one line in `ENGINES` (`imgsleuth/engines.py`).

## Useful options

```bash
imgsleuth img.jpg -e tineye,yandex        # pick engines
imgsleuth img.jpg -c anime                # only anime engines
imgsleuth https://site.com/pic.jpg        # URL input (all engines work)
imgsleuth img.jpg --host                  # temp-upload (1h) so URL-only engines work
imgsleuth img.jpg --social-only            # only results on social media
imgsleuth img.jpg --trim                  # strip borders from screenshots first
imgsleuth img.jpg --dir ~/Pictures        # also find copies in a local folder (offline)
imgsleuth img.jpg --open                  # open link-only engines in your browser
imgsleuth img.jpg --html r.html --json r.json --csv r.csv
imgsleuth img.jpg --proxy socks5://127.0.0.1:9050
```

## Social media

Results on Instagram, Facebook, TikTok, X, Reddit, Pinterest, YouTube,
LinkedIn, VK, Threads, Bluesky, Tumblr, Flickr and others are labelled with
the platform and listed first. Use `--social-only` (or the "Social media only"
box in the app) to see just those.

Social sites have no reverse image search of their own, so their posts come
through the engines above, mainly Yandex, Google Lens and Bing. Only public
posts those engines have indexed can be found; private accounts, stories and
most TikTok videos can't. The tool doesn't log in to any site.

## How accuracy works

Each candidate is scored 0–1 by combining pHash, dHash, aHash and an HSV
colour histogram, after auto-contrast and border trimming. The query is also
fingerprinted at 8 crop windows and mirrored, so cropped, flipped,
letterboxed, resized, recompressed, recoloured and watermarked copies still
match. Pages found by several engines are merged and ranked higher.

| score | verdict |
|---|---|
| ≥ 0.90 | exact copy / same image |
| ≥ 0.80 | strong — same image, edited |
| ≥ 0.68 | possible (default cut-off, `--min-score`) |

Benchmark (`python -m tests.benchmark`, 40 images × 14 edits):
**99.6% recall, 0 false positives in 1,560 different-image pairs.**
Covered edits: 25% resize, JPEG q20, 85/70% centre crop, 75% corner crop,
mirror, +40% brightness, low contrast, grayscale, watermark bar, 3° rotation,
letterbox, stretch, and a resize+JPEG+mirror combo.

Limits: it finds copies of the *same image*, not other photos of the same
subject. Large rotations (>~5°) and crops under ~65% may be missed.
Engines that only give a link (Google Lens, Bing) can't be verified.
Engine sites change their pages over time; a broken parser shows `[!]`
and the others keep working.

No face-recognition engines are included on purpose.

## Tests

```bash
pip install pytest && python -m pytest tests
```
