import math
import os
import re
from time import perf_counter

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

try:  # loading NLTK takes about a second: do it when the server starts, not on the first search
    import ranker.rank  # noqa: F401
except ImportError:
    pass

app = Flask(__name__)

PER_PAGE = 10
SNIPPET_LENGTH = 240


class SearchBackendUnavailable(RuntimeError):
    pass


def _snippet(description, text):
    content = description or text or ""
    return re.sub(r"\s+", " ", content).strip()[:SNIPPET_LENGTH]


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
            (SNIPPET_LENGTH, page_ids),
        )
        pages = {
            row[0]: {
                "id": row[0],
                "title": row[1] or row[2],
                "url": row[2],
                "snippet": _snippet(row[3], row[4]),
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