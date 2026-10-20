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


IR_BOOK_PAGE = """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
<HTML><HEAD><TITLE>Tokenization</TITLE></HEAD>
<BODY >
<!--Navigation Panel-->
<A NAME="tex2html1" HREF="next.html"><IMG ALT="next" SRC="next.png"></A>
<A NAME="tex2html2" HREF="up.html"><IMG ALT="up" SRC="up.png"></A>
<BR>
<B> Next:</B> <A HREF="next.html">Dropping common terms</A>
<B> Up:</B> <A HREF="up.html">Determining the vocabulary</A>
<B> Previous:</B> <A HREF="prev.html">Determining the vocabulary</A>
 &nbsp; <B>  <A HREF="contents.html">Contents</A></B>
 &nbsp; <B>  <A HREF="index.html">Index</A></B>
<BR>
<!--End of Navigation Panel-->
<H2>Tokenization</H2>
<P>""" + " ".join(["token"] * 40) + """</P>
<HR>
<!--Navigation Panel-->
<B> Next:</B> <A HREF="next.html">Dropping common terms</A>
<!--End of Navigation Panel-->
<ADDRESS>&copy; 2008 Cambridge University Press</ADDRESS>
</BODY></HTML>"""


def test_ir_book_navigation_and_footer_are_removed():
    result = extract_page(IR_BOOK_PAGE, "https://nlp.stanford.edu/IR-book/html/htmledition/tokenization-1.html")
    text = result["text"]
    for junk in ("Next:", "Up:", "Previous:", "Dropping common terms", "Contents", "Cambridge"):
        assert junk not in text
    assert text.startswith("Tokenization")
    assert result["word_count"] == 41


def test_unclosed_navigation_comment_keeps_the_page():
    html = f"<html><body><!--Navigation Panel--><p>{LONG}</p></body></html>"
    assert extract_page(html, "https://x.com/a")["word_count"] == 40


READ_THE_DOCS_PAGE = """<html lang="en"><head><title>Scrapy at a glance</title></head><body class="wy-body-for-nav">
<div class="wy-grid-for-nav">
  <nav data-toggle="wy-nav-shift" class="wy-nav-side"><div class="wy-side-scroll">Sidebar menu</div></nav>
  <section data-toggle="wy-nav-shift" class="wy-nav-content-wrap">
    <nav class="wy-nav-top" aria-label="Mobile navigation menu">Top menu</nav>
    <div class="wy-nav-content"><div class="rst-content">
      <div role="navigation" aria-label="Page navigation">Breadcrumbs</div>
      <div role="main" class="document" itemscope="itemscope">
        <div itemprop="articleBody"><h1>Scrapy at a glance</h1><p>""" + " ".join(["spider"] * 40) + """</p></div>
      </div>
      <footer>Previous Next</footer>
    </div></div>
  </section>
</div></body></html>"""


def test_read_the_docs_content_inside_nav_named_wrapper_is_kept():
    result = extract_page(READ_THE_DOCS_PAGE, "https://docs.scrapy.org/en/latest/intro/overview.html")
    assert result is not None
    assert result["text"].startswith("Scrapy at a glance")
    for junk in ("Sidebar menu", "Top menu", "Breadcrumbs", "Previous Next"):
        assert junk not in result["text"]
