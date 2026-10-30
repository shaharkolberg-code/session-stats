import json

from imgsleuth import engines
from imgsleuth.engines import Query, parse_iqdb, parse_saucenao, parse_tineye, parse_tracemoe, parse_yandex

IQDB_HTML = """<html><body><div id="pages">
<div><table><tr><th>Your image</th></tr><tr><td><img src="/thu/q.jpg"></td></tr></table></div>
<div><table><tr><th>Best match</th></tr>
<tr><td class="image"><a href="//danbooru.donmai.us/posts/123"><img src="/danbooru/1/ab.jpg" alt="Rating: s Tags: sky"></a></td></tr>
<tr><td>Danbooru</td></tr><tr><td>1200×800 [Safe]</td></tr><tr><td>96% similarity</td></tr></table></div>
<div><table><tr><th>Additional match</th></tr>
<tr><td class="image"><a href="https://gelbooru.com/x"><img src="https://g.example/t.jpg"></a></td></tr>
<tr><td>500x400</td></tr><tr><td>61% similarity</td></tr></table></div>
</div></body></html>"""


def test_parse_iqdb():
    m = parse_iqdb(IQDB_HTML)
    assert len(m) == 2
    assert m[0].page_url == "https://danbooru.donmai.us/posts/123"
    assert m[0].thumb_url == "https://iqdb.org/danbooru/1/ab.jpg"
    assert (m[0].width, m[0].height, m[0].engine_score) == (1200, 800, 0.96)
    assert m[1].engine_score == 0.61


def test_parse_tineye():
    payload = {"query_hash": "abc", "matches": [{
        "image_url": "https://img.tineye.com/r/1.jpg", "domain": "example.com", "width": 800,
        "height": 600, "score": 87.5,
        "backlinks": [{"url": "https://example.com/a.jpg", "backlink": "https://example.com/post"}]}]}
    [m] = parse_tineye(payload)
    assert m.page_url == "https://example.com/post" and m.image_url == "https://example.com/a.jpg"
    assert m.engine_score == 0.875 and m.width == 800


def test_parse_tracemoe():
    payload = {"result": [{"anilist": {"id": 21, "title": {"romaji": "One Piece"}}, "episode": 5,
                           "from": 125.4, "similarity": 0.95, "image": "https://media.trace.moe/i.jpg"}]}
    [m] = parse_tracemoe(payload)
    assert m.page_url == "https://anilist.co/anime/21"
    assert m.title == "One Piece ep 5 @ 2:05" and m.engine_score == 0.95


def test_parse_saucenao():
    payload = {"results": [{"header": {"similarity": "91.2", "thumbnail": "https://t/1.jpg", "index_name": "pixiv"},
                            "data": {"ext_urls": ["https://pixiv.net/a/1"], "title": "Sky"}}]}
    [m] = parse_saucenao(payload)
    assert m.page_url == "https://pixiv.net/a/1" and abs(m.engine_score - 0.912) < 1e-9


def test_parse_yandex():
    state = {"cbir": {"sites": [
        {"title": "A page", "url": "https://site.example/p",
         "originalImage": {"url": "https://site.example/full.jpg", "width": 1000, "height": 700},
         "thumb": {"url": "//avatars.mds.yandex.net/t"}},
        {"title": "dup", "url": "https://site.example/p"}]}}
    html = f"<div data-state='{json.dumps(state)}'></div><div data-state='not json'></div>"
    [m] = parse_yandex(html)
    assert m.image_url == "https://site.example/full.jpg" and m.width == 1000
    assert m.thumb_url == "https://avatars.mds.yandex.net/t"


def test_url_only_engines_need_url():
    q = Query(data=b"x", filename="a.jpg", url=None)
    assert engines.ENGINES["bing"].run(q, None, 1).status == "skipped"
    q.url = "https://ex.com/a b.jpg"
    r = engines.ENGINES["bing"].run(q, None, 1)
    assert r.status == "link" and "imgurl:https%3A%2F%2Fex.com%2Fa%20b.jpg" in r.search_url


def test_saucenao_without_key(monkeypatch):
    monkeypatch.delenv("SAUCENAO_API_KEY", raising=False)
    r = engines.saucenao(Query(data=b"x", filename="a.jpg", url=None), None, 1)
    assert r.status == "skipped"


def test_run_engine_catches_network_errors():
    def boom(q, s, t):
        import requests
        raise requests.ConnectionError()
    e = engines.Engine("x", "", "general", boom)
    r = engines.run_engine(e, Query(b"", "a", None), 1, None)
    assert r.status == "error" and r.error == "ConnectionError"
