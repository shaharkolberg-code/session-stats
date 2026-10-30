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

1. Install Python 3 from [python.org](https://python.org) (on Windows, tick "Add Python to PATH").
2. Download this folder (GitHub: **Code → Download ZIP**, then unzip).
3. Double-click the starter for your computer:
   - Mac: `Start Image Sleuth (Mac).command` (first time: right-click → Open)
   - Windows: `Start Image Sleuth (Windows).bat`
   - Linux: `Start Image Sleuth (Linux).sh`
4. Your browser opens. Tap **choose a photo** (or paste an image link) and press **Search**.

Results show as cards with a confidence score; tap one to open the page.
To use it from your phone on the same Wi-Fi, run `imgsleuth-app --lan` and open
`http://<your-computer's-IP>:8765` on the phone.

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
imgsleuth img.jpg --trim                  # strip borders from screenshots first
imgsleuth img.jpg --dir ~/Pictures        # also find copies in a local folder (offline)
imgsleuth img.jpg --open                  # open link-only engines in your browser
imgsleuth img.jpg --html r.html --json r.json --csv r.csv
imgsleuth img.jpg --proxy socks5://127.0.0.1:9050
```

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
