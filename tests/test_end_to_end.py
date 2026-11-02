"""End to end: pages in PostgreSQL -> indexer.build -> /search and /results return the expected first result.

Runs only when IRIS_TEST_DATABASE_URL points to a throw-away PostgreSQL database (it does in GitHub Actions).
Everything happens in a separate schema `iris_e2e`, which is dropped afterwards, so no real table is touched.
"""
import os
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

import pytest

from web import app as web_app

PAGES = [  # (url, site, title, text)
    ("https://e2e.test/inverted-index", "wikipedia", "Inverted index",
     "An inverted index maps every term to the pages that contain it. Search engines build an inverted index "
     "so a query only reads the postings of its own terms."),
    ("https://e2e.test/crawler", "wikipedia", "Web crawler",
     "A web crawler downloads pages, follows links and obeys robots.txt. The crawler feeds the index."),
    ("https://e2e.test/flask", "flask-docs", "Flask blueprints",
     "Blueprints organise a Flask application into parts. Each blueprint registers its own routes."),
    ("https://e2e.test/staff", "ciu", "Assoc. Prof. Dr. Tolga YIRTICI | CIU",
     "Tolga Yırtıcı teaches in the computer engineering department. Research on sign language recognition."),
]


def with_schema(url, schema):
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query["options"] = f"-csearch_path={schema}"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


@pytest.fixture
def e2e_database(monkeypatch):
    base = os.environ.get("IRIS_TEST_DATABASE_URL")
    if not base:
        pytest.skip("set IRIS_TEST_DATABASE_URL to run the end-to-end test on PostgreSQL")
    import psycopg2

    admin = psycopg2.connect(base)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS iris_e2e CASCADE")
        cur.execute("CREATE SCHEMA iris_e2e")
    url = with_schema(base, "iris_e2e")
    schema_sql = open(os.path.join(os.path.dirname(__file__), "..", "docs", "schema.sql"), encoding="utf-8").read()
    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        cur.execute(schema_sql)
        for page_url, site, title, text in PAGES:
            cur.execute("INSERT INTO pages (url, site, title, text, word_count, content_hash) "
                        "VALUES (%s, %s, %s, %s, %s, md5(%s))", (page_url, site, title, text, len(text.split()), text))

    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setattr(web_app, "_POOL", None)          # the web app opens a fresh pool on this database
    monkeypatch.setitem(web_app.app.config, "SEARCH_PROVIDER", None)
    yield url
    if web_app._POOL is not None:
        web_app._POOL.closeall()
    with admin.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS iris_e2e CASCADE")
    admin.close()


def test_index_then_search_returns_the_expected_first_result(e2e_database):
    from indexer.build import build_index

    result = build_index(e2e_database, force_full=True)
    assert result["documents"] == len(PAGES) and result["mode"] == "full"

    client = web_app.app.test_client()
    payload = client.get("/search?q=inverted+index").get_json()
    assert payload["total"] == 1
    assert payload["results"][0]["url"] == "https://e2e.test/inverted-index"
    assert payload["results"][0]["matched_terms"] == {"index": 2, "invert": 2}
    assert "<strong>" not in payload["results"][0]["snippet"]          # JSON stays plain text

    # Turkish name typed without Turkish letters; the title bonus puts the staff page first
    assert client.get("/search?q=tolga+yirtici").get_json()["results"][0]["url"] == "https://e2e.test/staff"

    # a word that is in no page: nothing is shown
    assert client.get("/search?q=inverted+football").get_json()["total"] == 0

    # site filter
    assert client.get("/search?q=blueprints&site=wikipedia").get_json()["total"] == 0
    assert client.get("/search?q=blueprints&site=flask-docs").get_json()["total"] == 1

    # the HTML page and the ranking-details page work on the same index
    html = client.get("/results?q=web+crawler").get_data(as_text=True)
    assert "https://e2e.test/crawler" in html and "<strong>crawler</strong>" in html
    first_id = client.get("/search?q=web+crawler").get_json()["results"][0]["id"]
    assert client.get(f"/explain?q=web+crawler&id={first_id}").status_code == 200


def test_incremental_build_picks_up_a_new_page(e2e_database):
    import psycopg2

    from indexer.build import build_index

    build_index(e2e_database, force_full=True)
    with psycopg2.connect(e2e_database) as conn, conn.cursor() as cur:
        text = "PostgreSQL stores the postings of the inverted index in a table."
        cur.execute("INSERT INTO pages (url, site, title, text, word_count, content_hash) "
                    "VALUES ('https://e2e.test/postgres', 'postgresql-docs', 'Postings table', %s, 11, md5(%s))",
                    (text, text))
    result = build_index(e2e_database)
    assert result["mode"] == "incremental" and result["changed_pages"] == 1
    payload = web_app.app.test_client().get("/search?q=postings+table").get_json()
    assert payload["results"][0]["url"] == "https://e2e.test/postgres"
