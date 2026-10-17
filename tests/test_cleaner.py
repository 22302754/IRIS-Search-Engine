"""Unit tests for the crawler's text cleaner (crawler/cleaner.py)."""
from crawler.cleaner import canonicalize, content_hash, extract_page, normalize_text

LONG = " ".join(["retrieval"] * 40)


def page(main, extra_head="", extra_body="", lang="en"):
    return f"""<html lang="{lang}"><head><title> My Page </title>{extra_head}</head><body>
    <header>Site header Sign in</header><nav>Home Docs Blog</nav>
    <main>{main}</main>
    <footer>Copyright footer</footer><script>var secret = 1;</script></body></html>"""


def test_keeps_main_text_and_title():
    result = extract_page(page(f"<p>{LONG}</p>"), "https://x.com/a")
    assert result["title"] == "My Page"
    assert result["text"].startswith("retrieval retrieval")
    assert result["word_count"] == 40


def test_removes_menus_footer_and_scripts():
    result = extract_page(page(f"<p>{LONG}</p>"), "https://x.com/a")
    for junk in ("Site header", "Home Docs", "Copyright", "secret"):
        assert junk not in result["text"]


def test_removes_boilerplate_found_by_class_and_role():
    main = (f'<p>{LONG}</p><div class="sidebar">SIDEBAR</div>'
            f'<div id="cookie-banner">COOKIES</div><div role="navigation">NAVROLE</div>')
    text = extract_page(page(main), "https://x.com/a")["text"]
    assert "SIDEBAR" not in text and "COOKIES" not in text and "NAVROLE" not in text


def test_paragraphs_do_not_stick_together():
    main = f"<p>{LONG} end</p><p>start {LONG}</p>"
    text = extract_page(page(main), "https://x.com/a")["text"]
    assert "endstart" not in text
    assert "end\nstart" in text


def test_description_and_language():
    head = '<meta name="description" content="A short summary">'
    result = extract_page(page(f"<p>{LONG}</p>", extra_head=head, lang="en-GB"), "https://x.com/a")
    assert result["description"] == "A short summary"
    assert result["language"] == "en"


def test_falls_back_to_body_without_main():
    html = f"<html><head><title>T</title></head><body><div><p>{LONG}</p></div></body></html>"
    assert extract_page(html, "https://x.com/a")["word_count"] == 40


def test_thin_and_empty_pages_are_rejected():
    assert extract_page(page("<p>Moved.</p>"), "https://x.com/a") is None
    assert extract_page("", "https://x.com/a") is None
    assert extract_page("   ", "https://x.com/a") is None


def test_normalize_text_collapses_spaces_and_blank_lines():
    assert normalize_text("  a   b \n\n\n  c\t d ") == "a b\nc d"


def test_canonicalize_url():
    assert canonicalize("HTTPS://Example.COM:443/Path?b=2&a=1#top") == "https://example.com/Path?a=1&b=2"
    assert canonicalize("https://example.com/p?utm_source=x&id=5") == "https://example.com/p?id=5"
    assert canonicalize("http://example.com") == "http://example.com/"
    assert canonicalize("http://localhost:8000/a") == "http://localhost:8000/a"


def test_content_hash_ignores_case_and_spaces():
    assert content_hash("Hello   World\n") == content_hash("hello world")
    assert content_hash("hello world") != content_hash("hello there")
