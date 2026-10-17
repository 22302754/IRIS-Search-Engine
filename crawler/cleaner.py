"""
IRIS - text cleaning and duplicate helpers used by the crawler.

extract_page(html, url) -> dict with title, text, description, language, word_count
                           (or None when the page has too little real text)
canonicalize(url)       -> one standard form of a URL, so the same page is not crawled twice
content_hash(text)      -> fingerprint of the page text, so copies at different URLs are skipped
"""
import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import lxml.html

MIN_WORDS = 30  # pages with fewer words are menus, redirects or empty pages

# Elements that never contain article text
DROP_TAGS = [
    "script", "style", "noscript", "template", "svg", "canvas", "iframe",
    "nav", "header", "footer", "aside", "form", "button", "select", "input", "textarea",
]
# ARIA roles used for menus, site headers and footers
DROP_ROLES = {"navigation", "banner", "contentinfo", "search", "complementary", "dialog"}
# class / id words that mark boilerplate (menus, sidebars, cookie bars, ads, edit links ...)
BOILERPLATE = re.compile(
    r"(?:^|[\s_-])(?:sidebar|sidebar-inner|menu|navbar|navbox|nav|breadcrumbs?|cookie|banner|advert|ads|"
    r"social|share|sharing|related|footer|header|toc|skip|popup|newsletter|comments?|"
    r"editsection|mw-editsection|reflist|noprint|mw-jump-link|catlinks|printfooter)(?:$|[\s_-])",
    re.IGNORECASE,
)
PROTECTED = {"html", "body", "main", "article"}
# Where the real content usually lives, most specific first
MAIN_SELECTORS = [
    "//main", "//article", "//*[@role='main']", "//*[@id='main-content']",
    "//*[@id='mw-content-text']", "//*[@id='bodyContent']", "//*[@id='content']",
]
BLOCK_TAGS = {
    "p", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "br", "tr", "td", "th",
    "pre", "section", "dd", "dt", "dl", "blockquote", "table", "figcaption", "hr",
}
TRACKING_PARAMS = re.compile(r"^(utm_\w+|fbclid|gclid|mc_cid|mc_eid|ref|source)$", re.IGNORECASE)


# --------------------------------------------------------------------------- URLs
def canonicalize(url):
    """Lower-case scheme and host, drop #fragment, default ports and tracking params, sort the query."""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = parts.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        host = f"{host}:{port}"
    path = parts.path or "/"
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                             if not TRACKING_PARAMS.match(k)))
    return urlunsplit((scheme, host, path, query, ""))


# --------------------------------------------------------------------------- text
def normalize_text(text):
    """Collapse spaces inside each line, drop empty lines."""
    lines = (re.sub(r"\s+", " ", line).strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def content_hash(text):
    """SHA-1 of the text with case and whitespace ignored."""
    key = re.sub(r"\s+", " ", text).strip().lower()
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def _first_text(doc, xpaths):
    for xp in xpaths:
        found = doc.xpath(xp)
        if found:
            value = found[0] if isinstance(found[0], str) else found[0].text_content()
            value = re.sub(r"\s+", " ", value).strip()
            if value:
                return value
    return ""


def _is_boilerplate(el):
    if el.tag in PROTECTED:
        return False
    if (el.get("role") or "").lower() in DROP_ROLES:
        return True
    if el.get("aria-hidden") == "true" or el.get("hidden") is not None:
        return True
    marks = f"{el.get('class') or ''} {el.get('id') or ''}"
    return bool(marks.strip()) and bool(BOILERPLATE.search(marks))


def extract_page(html, url, min_words=MIN_WORDS):
    """Return the clean content of one HTML page, or None if it is too thin to index."""
    if not html or not html.strip():
        return None
    try:
        doc = lxml.html.fromstring(html)
    except (ValueError, lxml.etree.ParserError):
        return None

    title = _first_text(doc, ["//title", "//meta[@property='og:title']/@content", "//h1"])
    description = _first_text(doc, [
        "//meta[@name='description']/@content",
        "//meta[@property='og:description']/@content",
    ])
    language = (doc.get("lang") or doc.get("xml:lang") or "").split("-")[0].lower() or "unknown"

    # 1. remove tags that never hold content
    for el in doc.xpath("//" + " | //".join(DROP_TAGS)):
        el.drop_tree()
    # 2. remove menus, sidebars, cookie bars, ... found by role / class / id
    for el in [e for e in doc.iter() if isinstance(e.tag, str) and _is_boilerplate(e)]:
        if el.getparent() is not None:
            el.drop_tree()

    # 3. keep only the main content area when the page marks one
    main = None
    for xp in MAIN_SELECTORS:
        found = doc.xpath(xp)
        if found:
            main = found[0]
            break
    if main is None:
        body = doc.xpath("//body")
        main = body[0] if body else doc

    # 4. block elements end with a line break so words from different paragraphs don't stick together
    for el in main.iter():
        if isinstance(el.tag, str) and el.tag in BLOCK_TAGS:
            el.tail = "\n" + (el.tail or "")

    text = normalize_text(main.text_content())
    word_count = len(text.split())
    if word_count < min_words:
        return None

    return {
        "url": url,
        "title": title[:500],
        "description": description[:1000],
        "language": language,
        "text": text,
        "word_count": word_count,
        "content_hash": content_hash(text),
    }
