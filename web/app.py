import math
import os
import re
from contextlib import closing
from time import perf_counter

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

app = Flask(__name__)

PER_PAGE = 10
SNIPPET_LENGTH = 240


class SearchBackendUnavailable(RuntimeError):
    pass


def _snippet(description, text):
    content = description or text or ""
    return re.sub(r"\s+", " ", content).strip()[:SNIPPET_LENGTH]


def _search_database(query):
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SearchBackendUnavailable("Search database is not configured")

    try:
        import psycopg2
        from ranker.rank import rank
    except ImportError as exc:
        raise SearchBackendUnavailable("Search backend is not installed") from exc

    try:
        with closing(psycopg2.connect(database_url)) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM pages")
                document_count = cursor.fetchone()[0]

        if not document_count:
            return []

        ranked_pages = rank(query, k=document_count)
        if not ranked_pages:
            return []

        page_ids = [page_id for page_id, _ in ranked_pages]
        with closing(psycopg2.connect(database_url)) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, title, url, description, text
                    FROM pages
                    WHERE id = ANY(%s)
                    """,
                    (page_ids,),
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
    except psycopg2.Error as exc:
        raise SearchBackendUnavailable("Search database is unavailable") from exc

    return [
        {**pages[page_id], "score": float(score)}
        for page_id, score in ranked_pages
        if page_id in pages
    ]


def execute_search(query, page=1):
    started = perf_counter()
    provider = app.config.get("SEARCH_PROVIDER") or _search_database
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