import io

from PIL import ImageOps

from imgsleuth import cli, verify
from imgsleuth.engines import ENGINES, EngineResult, Engine, Match
from imgsleuth.fingerprint import fingerprint, similarity
from imgsleuth.local import search_folder

from .synth import jpeg, make_image


def test_identical_and_different():
    a, b = make_image(1), make_image(2)
    fa = fingerprint(a)
    assert similarity(fa, fingerprint(a, crops=False))["score"] > 0.99
    assert similarity(fa, fingerprint(b, crops=False))["score"] < 0.6


def test_local_folder_search(tmp_path):
    q = make_image(7)
    q.save(tmp_path / "query.png")
    jpeg(ImageOps.mirror(q.resize((200, 150))), 35).save(tmp_path / "copy.jpg")
    for s in range(3):
        make_image(100 + s).save(tmp_path / f"other{s}.png")
    (tmp_path / "broken.jpg").write_bytes(b"not an image")
    res = search_folder(str(tmp_path), fingerprint(q), 0.68, exclude=tmp_path / "query.png")
    assert [m.title for m in res] == ["copy.jpg"]


def test_merge_combines_engines():
    a = Match("tineye", page_url="https://www.ex.com/p/", verified_score=0.9)
    b = Match("yandex", page_url="https://ex.com/p", verified_score=0.95, image_url="https://ex.com/i.jpg")
    c = Match("iqdb", page_url="https://other.com/x", engine_score=0.5)
    out = verify.merge([a, b, c])
    assert len(out) == 2 and set(out[0].engines) == {"tineye", "yandex"}
    assert out[0].verified_score == 0.95 and out[0].image_url == "https://ex.com/i.jpg"


def test_cli_end_to_end(tmp_path, monkeypatch, capsys):
    """Fake engine returns a real copy and an unrelated image; verification must sort them out."""
    q = make_image(3)
    q.save(tmp_path / "q.jpg")
    copy_bytes, other_bytes = io.BytesIO(), io.BytesIO()
    jpeg(q.resize((300, 225)), 50).save(copy_bytes, "JPEG")
    make_image(99).save(other_bytes, "JPEG")
    files = {"https://cdn/copy.jpg": copy_bytes.getvalue(), "https://cdn/other.jpg": other_bytes.getvalue()}

    def fake(qr, s, t):
        return EngineResult("fake", "found", "https://fake/search", [
            Match("fake", page_url="https://a.com/1", image_url="https://cdn/other.jpg", engine_score=0.99),
            Match("fake", page_url="https://b.com/2", image_url="https://cdn/copy.jpg", engine_score=0.5),
        ])
    monkeypatch.setitem(ENGINES, "fake", Engine("fake", "", "general", fake))
    monkeypatch.setattr(verify, "fetch_image", lambda url, *a, **k: files.get(url))
    out = tmp_path / "r.json"
    rc = cli.main([str(tmp_path / "q.jpg"), "-e", "fake", "-q", "--json", str(out),
                   "--html", str(tmp_path / "r.html"), "--csv", str(tmp_path / "r.csv")])
    assert rc == 0
    import json
    rep = json.loads(out.read_text())
    assert [m["page_url"] for m in rep["matches"]] == ["https://b.com/2"]  # unrelated one filtered
    assert rep["matches"][0]["verdict"] == "exact"
    assert "Image Sleuth Report" in (tmp_path / "r.html").read_text()
    assert "b.com" in capsys.readouterr().out
