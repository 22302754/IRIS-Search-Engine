import math
import os
import re
from time import perf_counter

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from markupsafe import Markup, escape

load_dotenv()

try:  # loading NLTK takes about a second: do it when the server starts, not on the first search
    import ranker.rank  # noqa: F401
except ImportError:
    pass

app = Flask(__name__)
app.jinja_env.filters["highlight"] = lambda value, query: highlight(value, query)

PER_PAGE = 10
SNIPPET_WORDS = 30          # words shown around the first query word
SNIPPET_BEFORE = 10         # words kept before it


class SearchBackendUnavailable(RuntimeError):
    pass


def _query_terms(query):
    """The query's terms exactly as the ranker searches for them (same preprocess)."""
    try:
        from preprocessing.preprocess import preprocess
    except ImportError:
        return {word.lower() for word in re.findall(r"[A-Za-z]+", query or "")}
    return set(preprocess(query or ""))


def _is_query_word(word, terms):
    """True when a word of the page is one of the query terms after stemming."""
    letters = re.sub(r"[^a-z]", "", word.lower())
    if not letters or not terms:
        return False
    # quick test first: a Porter stem almost always starts like the word itself
    if not any(letters.startswith(term[:3]) for term in terms):
        return False
    try:
        from preprocessing.preprocess import preprocess
        return any(token in terms for token in preprocess(letters))
    except ImportError:
        return letters in terms


def _snippet(description, text, query=""):
    """About 30 words of the page around the first query word; the description or the start of the text
    when the page does not contain a query word."""
    words = (text or "").split()
    terms = _query_terms(query)
    for i, word in enumerate(words):
        if _is_query_word(word, terms):
            start = max(0, i - SNIPPET_BEFORE)
            part = words[start:start + SNIPPET_WORDS]
            prefix = "… " if start > 0 else ""
            suffix = " …" if start + SNIPPET_WORDS < len(words) else ""
            return prefix + " ".join(part) + suffix
    fallback = (description or "").split() or words
    return " ".join(fallback[:SNIPPET_WORDS]) + (" …" if len(fallback) > SNIPPET_WORDS else "")


def highlight(value, query):
    """HTML-escaped text with the query words in <strong> (used by the results page)."""
    terms = _query_terms(query)
    pieces = re.split(r"(\s+)", value or "")
    return Markup("".join(
        f"<strong>{escape(piece)}</strong>" if piece.strip() and _is_query_word(piece, terms) else str(escape(piece))
        for piece in pieces
    ))


_POOL = None
_POOL_URL = None


def _connection_pool(database_url):
    """One small pool per worker process: opening a new TLS connection to the cloud database
    for every search took most of the response time, so connections are reused."""
    global _POOL, _POOL_URL
    if _POOL is None or _POOL_URL != database_url:
        from psycopg2.pool import ThreadedConnectionPool

        _POOL = ThreadedConnectionPool(1, 4, database_url, connect_timeout=10)
        _POOL_URL = database_url
    return _POOL


SITE_LABELS = {
    "books": "Books to Scrape", "quotes": "Quotes to Scrape", "python-docs": "Python docs", "mdn": "MDN Web Docs",
    "ir-book": "IR textbook (Stanford)", "wikipedia": "Wikipedia", "postgresql-docs": "PostgreSQL docs",
    "scrapy-docs": "Scrapy docs", "flask-docs": "Flask docs", "ciu": "CIU website",
}


def _site_param():
    site = request.args.get("site", "").strip()
    return site if site in SITE_LABELS else ""


def _run_search(connection, query, page, site=""):
    """One page of results in two database round trips (ranker/search.py)."""
    from ranker.search import search_page

    page = max(page, 1)
    total, found = search_page(connection, query, page, PER_PAGE, site or None)
    total_pages = max(1, math.ceil(total / PER_PAGE))
    if page > total_pages:                        # asked for a page past the end: show the last one
        page = total_pages
        total, found = search_page(connection, query, page, PER_PAGE, site or None)

    page_results, pages = [], {}
    for r in found:
        text = r["text_part"]
        if r["part_is_cut"]:                      # the part starts inside the page: drop the cut first word
            text = text.split(" ", 1)[1] if " " in text else text
        snippet = _snippet(r["description"], text, query)
        if r["part_is_cut"] and not snippet.startswith("… ") and text and snippet.startswith(text.split()[0]):
            snippet = "… " + snippet
        page_results.append((r["id"], r["score"]))
        pages[r["id"]] = {"id": r["id"], "title": r["title"], "url": r["url"], "snippet": snippet,
                          "site": r["site"], "matched_terms": r["matched_terms"]}
    return total, page, total_pages, page_results, pages


def _with_connection(work):
    """Run work(connection) on a pooled connection; one retry if the server closed an idle connection."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SearchBackendUnavailable("Search database is not configured")

    try:
        import psycopg2
        import ranker.rank  # noqa: F401  (fail early if the backend is missing)
    except ImportError as exc:
        raise SearchBackendUnavailable("Search backend is not installed") from exc

    for attempt in (1, 2):
        connection = None
        broken = False
        try:
            pool = _connection_pool(database_url)
            connection = pool.getconn()
            connection.autocommit = True
            return work(connection)
        except psycopg2.Error as exc:
            broken = True
            if attempt == 2:
                raise SearchBackendUnavailable("Search database is unavailable") from exc
        finally:
            if connection is not None:
                _POOL.putconn(connection, close=broken or bool(connection.closed))


def _search_database(query, page=1, site=""):
    total, page, total_pages, page_results, pages = _with_connection(
        lambda connection: _run_search(connection, query, page, site))
    return {
        "query": query,
        "site": site or None,
        "total": total,
        "page": page,
        "per_page": PER_PAGE,
        "time_ms": 0,
        "results": [
            {**pages[page_id], "score": float(score)}
            for page_id, score in page_results
            if page_id in pages
        ],
        "total_pages": total_pages,
    }


def execute_search(query, page=1, site=""):
    started = perf_counter()
    provider = app.config.get("SEARCH_PROVIDER")
    if provider is None:
        payload = _search_database(query, page, site)
        payload["time_ms"] = round((perf_counter() - started) * 1000)
        return payload

    ranked_results = provider(query)
    if site:
        ranked_results = [r for r in ranked_results if r.get("site") == site]
    total = len(ranked_results)
    total_pages = max(1, math.ceil(total / PER_PAGE))
    page = min(max(page, 1), total_pages)
    start = (page - 1) * PER_PAGE

    return {
        "query": query,
        "site": site or None,
        "total": total,
        "page": page,
        "per_page": PER_PAGE,
        "time_ms": round((perf_counter() - started) * 1000),
        "results": ranked_results[start:start + PER_PAGE],
        "total_pages": total_pages,
    }


@app.route("/")
def home():
    return render_template("search.html", sites=SITE_LABELS, site="")


@app.route("/results")
def results():
    query = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int) or 1
    site = _site_param()
    search_error = False

    if query:
        try:
            payload = execute_search(query, page, site)
        except SearchBackendUnavailable:
            payload = {
                "query": query,
                "total": 0,
                "page": 1,
                "time_ms": 0,
                "results": [],
                "total_pages": 1,
            }
            search_error = True
    else:
        payload = {
            "query": query,
            "total": 0,
            "page": 1,
            "time_ms": 0,
            "results": [],
            "total_pages": 1,
        }

    payload.setdefault("site", site or None)
    response = render_template("results.html", **payload, search_error=search_error,
                               sites=SITE_LABELS, site_labels=SITE_LABELS)
    return response, 503 if search_error else 200


@app.route("/search")
def search_api():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "empty query"}), 400

    page = request.args.get("page", 1, type=int) or 1
    try:
        payload = execute_search(query, page, _site_param())
    except SearchBackendUnavailable:
        return jsonify({"error": "search backend unavailable"}), 503

    payload.pop("total_pages")
    return jsonify(payload)


@app.route("/explain")
def explain_page():
    """Every number behind one result's score: TF, DF, IDF, weights and the cosine formula."""
    query = request.args.get("q", "").strip()
    page_id = request.args.get("id", type=int)
    if not query or page_id is None:
        return render_template("explain.html", query=query, data=None, error="missing"), 400
    try:
        from ranker.explain import explain

        def work(connection):
            with connection.cursor() as cursor:
                return explain(cursor, query, page_id)

        data = _with_connection(work)
    except SearchBackendUnavailable:
        return render_template("explain.html", query=query, data=None, error="offline"), 503
    if data is None:
        return render_template("explain.html", query=query, data=None, error="notfound"), 404
    return render_template("explain.html", query=query, data=data, error=None, site_labels=SITE_LABELS)


if __name__ == "__main__":
    app.run(debug=True)