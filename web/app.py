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
TEXT_FOR_SNIPPET = 20000    # characters of page text read for the snippet


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


def _run_search(connection, query, page):
    from ranker.rank import rank

    ranked_pages = rank(query, k=None, connection=connection)
    total = len(ranked_pages)
    total_pages = max(1, math.ceil(total / PER_PAGE))
    page = min(max(page, 1), total_pages)
    start = (page - 1) * PER_PAGE
    page_results = ranked_pages[start:start + PER_PAGE]
    page_ids = [page_id for page_id, _ in page_results]

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, title, url, description, LEFT(text, %s)
            FROM pages
            WHERE id = ANY(%s)
            """,
            (TEXT_FOR_SNIPPET, page_ids),
        )
        pages = {
            row[0]: {
                "id": row[0],
                "title": row[1] or row[2],
                "url": row[2],
                "snippet": _snippet(row[3], row[4], query),
            }
            for row in cursor.fetchall()
        }
    return total, page, total_pages, page_results, pages


def _search_database(query, page=1):
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SearchBackendUnavailable("Search database is not configured")

    try:
        import psycopg2
        import ranker.rank  # noqa: F401  (fail early if the backend is missing)
    except ImportError as exc:
        raise SearchBackendUnavailable("Search backend is not installed") from exc

    # Two attempts: a pooled connection may have been closed by the server while idle.
    for attempt in (1, 2):
        connection = None
        broken = False
        try:
            pool = _connection_pool(database_url)
            connection = pool.getconn()
            connection.autocommit = True
            total, page, total_pages, page_results, pages = _run_search(connection, query, page)
            break
        except psycopg2.Error as exc:
            broken = True
            if attempt == 2:
                raise SearchBackendUnavailable("Search database is unavailable") from exc
        finally:
            if connection is not None:
                _POOL.putconn(connection, close=broken or bool(connection.closed))

    return {
        "query": query,
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


def execute_search(query, page=1):
    started = perf_counter()
    provider = app.config.get("SEARCH_PROVIDER")
    if provider is None:
        payload = _search_database(query, page)
        payload["time_ms"] = round((perf_counter() - started) * 1000)
        return payload

    ranked_results = provider(query)
    total = len(ranked_results)
    total_pages = max(1, math.ceil(total / PER_PAGE))
    page = min(max(page, 1), total_pages)
    start = (page - 1) * PER_PAGE

    return {
        "query": query,
        "total": total,
        "page": page,
        "per_page": PER_PAGE,
        "time_ms": round((perf_counter() - started) * 1000),
        "results": ranked_results[start:start + PER_PAGE],
        "total_pages": total_pages,
    }


@app.route("/")
def home():
    return render_template("search.html")


@app.route("/results")
def results():
    query = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int) or 1
    search_error = False

    if query:
        try:
            payload = execute_search(query, page)
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

    response = render_template("results.html", **payload, search_error=search_error)
    return response, 503 if search_error else 200


@app.route("/search")
def search_api():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "empty query"}), 400

    page = request.args.get("page", 1, type=int) or 1
    try:
        payload = execute_search(query, page)
    except SearchBackendUnavailable:
        return jsonify({"error": "search backend unavailable"}), 503

    payload.pop("total_pages")
    return jsonify(payload)


if __name__ == "__main__":
    app.run(debug=True)