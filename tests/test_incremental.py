"""Unit tests for the incremental re-crawl and the per-site rules (crawler/iris_spider.py)."""
import json
from pathlib import Path

import scrapy
from scrapy.http import HtmlResponse, Request, Response

from crawler.cleaner import content_hash, extract_page
from crawler.iris_spider import IrisSpider, load_rules

ROOT = Path(__file__).resolve().parents[1]
WORDS = " ".join(["retrieval"] * 40)


def make_spider(tmp_path, max_pages=10, max_depth=2):
    seeds = tmp_path / "seeds.txt"
    seeds.write_text("https://site.test/\n")
    sites = tmp_path / "sites.json"
    sites.write_text(json.dumps({"defaults": {"language": "en"}, "sites": [
        {"name": "site", "host": "site.test", "max_pages": max_pages, "max_depth": max_depth, "allow": ["^/"]}]}))
    return IrisSpider(seeds=str(seeds), sites=str(sites))


def html(body_words=WORDS, links=""):
    return f"<html><head><title>T</title></head><body><main><p>{body_words}</p>{links}</main></body></html>"


def response(url, body, depth=0, status=200):
    req = Request(url, meta={"site": "site", "depth": depth})
    if status == 304:
        return Response(url, status=304, request=req)
    return HtmlResponse(url, body=body.encode(), encoding="utf-8", request=req,
                        headers={"Content-Type": "text/html", "ETag": '"v1"'})


def pages_of(output):
    return [x for x in output if isinstance(x, dict)]


def test_new_page_is_saved_with_default_language(tmp_path):
    spider = make_spider(tmp_path)
    items = pages_of(spider.parse(response("https://site.test/a", html())))
    assert len(items) == 1
    assert items[0]["action"] == "new"
    assert items[0]["language"] == "en"            # page has no lang attribute -> site default
    assert items[0]["etag"] == '"v1"'
    assert spider.result["site"]["new"] == 1


def test_unchanged_known_page_is_not_written_again(tmp_path):
    spider = make_spider(tmp_path)
    old_hash = extract_page(html(), "https://site.test/a")["content_hash"]
    spider.load_known([{"url": "https://site.test/a", "content_hash": old_hash}])
    items = pages_of(spider.parse(response("https://site.test/a", html())))
    assert items == []
    assert spider.result["site"]["unchanged"] == 1


def test_changed_known_page_is_written_as_update(tmp_path):
    spider = make_spider(tmp_path)
    spider.load_known([{"url": "https://site.test/a", "content_hash": content_hash("old text")}])
    items = pages_of(spider.parse(response("https://site.test/a", html(WORDS + " changed"))))
    assert len(items) == 1 and items[0]["action"] == "update"
    assert spider.result["site"]["updated"] == 1


def test_not_modified_answer_counts_as_unchanged(tmp_path):
    spider = make_spider(tmp_path)
    assert pages_of(spider.parse(response("https://site.test/a", "", status=304))) == []
    assert spider.result["site"]["unchanged"] == 1


def test_known_leaf_pages_are_requested_conditionally(tmp_path):
    spider = make_spider(tmp_path, max_depth=1)
    spider.load_known([{"url": "https://site.test/b", "content_hash": "x", "etag": '"e1"',
                        "last_modified": "Mon, 19 Oct 2026 10:00:00 GMT"}])
    out = list(spider.parse(response("https://site.test/", html(links='<a href="/b">b</a><a href="/c">c</a>'))))
    requests = {r.url: r for r in out if isinstance(r, scrapy.Request)}
    leaf_known, leaf_new = requests["https://site.test/b"], requests["https://site.test/c"]
    assert leaf_known.headers.get("If-None-Match") == b'"e1"'
    assert leaf_known.meta["handle_httpstatus_list"] == [304]
    assert "If-None-Match" not in leaf_new.headers


def test_old_pages_count_towards_the_collection_size(tmp_path):
    spider = make_spider(tmp_path, max_pages=2)
    spider.load_known([{"url": "https://site.test/a", "content_hash": content_hash("old a")},
                       {"url": "https://site.test/b", "content_hash": content_hash("old b")}])
    list(spider.start_requests())                     # counts the old pages per site
    assert spider.site_is_full("site")
    assert list(spider.parse(response("https://site.test/z", html()))) == []        # no room for new pages
    assert spider.wants("https://site.test/a", "site")                              # old pages are still checked
    assert pages_of(spider.parse(response("https://site.test/a", html())))[0]["action"] == "update"


def test_real_site_config_is_valid():
    rules = load_rules(ROOT / "crawler" / "seeds.txt", ROOT / "crawler" / "sites.json")
    assert len(rules) == 9
    assert all(r.accepts(r.start_url) for r in rules)
    assert 3000 <= sum(r.max_pages for r in rules) <= 5000


def test_html_with_wrong_content_type_is_still_read(tmp_path):
    spider = make_spider(tmp_path)
    req = Request("https://site.test/doc", meta={"site": "site", "depth": 0})
    resp = Response("https://site.test/doc", body=("<!DOCTYPE html>" + html()).encode(), request=req,
                    headers={"Content-Type": "application/octet-stream"})
    assert len(pages_of(spider.parse(resp))) == 1


def test_real_non_html_is_skipped(tmp_path):
    spider = make_spider(tmp_path)
    req = Request("https://site.test/file.pdf", meta={"site": "site", "depth": 0})
    resp = Response("https://site.test/file.pdf", body=b"%PDF-1.4", request=req,
                    headers={"Content-Type": "application/pdf"})
    assert list(spider.parse(resp)) == []
    assert spider.skipped["not_html"] == 1
