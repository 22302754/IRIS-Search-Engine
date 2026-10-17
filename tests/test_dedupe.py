"""Unit tests for duplicate control (crawler/dedupe.py) and the site rules of the spider."""
import json

from crawler.dedupe import Deduplicator
from crawler.iris_spider import load_rules


def test_same_url_is_new_only_once():
    d = Deduplicator()
    assert d.is_new_url("https://x.com/a")
    assert not d.is_new_url("https://x.com/a")


def test_url_variants_count_as_the_same_page():
    d = Deduplicator()
    assert d.is_new_url("https://x.com/a?b=1&c=2")
    assert not d.is_new_url("https://X.com/a?c=2&b=1#part")
    assert not d.is_new_url("https://x.com/a?b=1&c=2&utm_source=mail")


def test_same_text_is_new_only_once():
    d = Deduplicator()
    assert d.is_new_content("abc123")
    assert not d.is_new_content("abc123")
    assert not d.is_new_content("")


def test_pages_from_earlier_runs_are_known():
    d = Deduplicator()
    d.load(urls=["https://x.com/old"], hashes=["h1", None])
    assert not d.is_new_url("https://x.com/old")
    assert not d.is_new_content("h1")
    assert d.is_new_url("https://x.com/new")


def write_config(tmp_path):
    seeds = tmp_path / "seeds.txt"
    seeds.write_text("# comment\nhttps://docs.example.org/3/\nhttps://other.org/blog/\n")
    sites = tmp_path / "sites.json"
    sites.write_text(json.dumps({
        "defaults": {"max_pages": 10, "max_depth": 2, "deny": [r"\.pdf$"]},
        "sites": [{"name": "docs", "host": "docs.example.org", "max_pages": 50,
                   "allow": ["^/3/"], "deny": ["^/3/genindex"]}],
    }))
    return seeds, sites


def test_site_rules_follow_allow_and_deny(tmp_path):
    seeds, sites = write_config(tmp_path)
    docs, other = load_rules(seeds, sites)
    assert docs.name == "docs" and docs.max_pages == 50 and docs.max_depth == 2
    assert docs.accepts("https://docs.example.org/3/tutorial/")
    assert not docs.accepts("https://docs.example.org/2/tutorial/")      # not allowed
    assert not docs.accepts("https://docs.example.org/3/genindex.html")  # site deny
    assert not docs.accepts("https://docs.example.org/3/guide.pdf")      # default deny
    assert not docs.accepts("https://evil.com/3/tutorial/")              # other host
    # a seed without its own rules stays under its own path
    assert other.name == "other.org" and other.max_pages == 10
    assert other.accepts("https://other.org/blog/post-1")
    assert not other.accepts("https://other.org/shop/")


def test_only_and_max_pages_options(tmp_path):
    seeds, sites = write_config(tmp_path)
    rules = load_rules(seeds, sites, only={"docs"}, max_pages=5)
    assert [r.name for r in rules] == ["docs"]
    assert rules[0].max_pages == 5
