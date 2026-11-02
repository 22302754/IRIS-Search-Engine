"""All-words rule, site filter and ranking details (ranker/explain.py and the web routes)."""
import os

import pytest

from indexer.build import _prepare_index
from ranker.rank import rank
from web.app import app

DOCS = [  # (id, site, text)
    (1, "wikipedia", "web crawler web"),
    (2, "ir-book", "web index"),
    (3, "ir-book", "index rank rank"),
]


@pytest.fixture
def db():
    url = os.environ.get("IRIS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("set IRIS_TEST_DATABASE_URL to run the ranking-detail tests on PostgreSQL")
    import psycopg2

    conn = psycopg2.connect(url)
    term_frequencies, document_frequencies, norms = _prepare_index([(i, text) for i, _, text in DOCS])
    with conn.cursor() as cur:   # TEMP tables hide any real tables and disappear with the connection
        cur.execute("CREATE TEMP TABLE pages (id INTEGER PRIMARY KEY, url TEXT, title TEXT, site TEXT, "
                    "word_count INTEGER, text TEXT)")
        cur.execute("CREATE TEMP TABLE terms (id SERIAL PRIMARY KEY, term TEXT UNIQUE, doc_freq INTEGER)")
        cur.execute("CREATE TEMP TABLE postings (term_id INTEGER, page_id INTEGER, tf INTEGER, "
                    "PRIMARY KEY (term_id, page_id))")
        cur.execute("CREATE TEMP TABLE page_norms (page_id INTEGER PRIMARY KEY, norm DOUBLE PRECISION)")
        for i, site, text in DOCS:
            cur.execute("INSERT INTO pages VALUES (%s, %s, %s, %s, %s, %s)",
                        (i, f"https://site.test/{i}", f"Page {i}", site, len(text.split()), text))
        for term, df in sorted(document_frequencies.items()):
            cur.execute("INSERT INTO terms (term, doc_freq) VALUES (%s, %s) RETURNING id", (term, df))
            term_id = cur.fetchone()[0]
            for page_id, counts in term_frequencies.items():
                if term in counts:
                    cur.execute("INSERT INTO postings VALUES (%s, %s, %s)", (term_id, page_id, counts[term]))
        cur.executemany("INSERT INTO page_norms VALUES (%s, %s)", list(norms.items()))
    yield conn
    conn.close()


def test_only_pages_with_every_query_word_are_kept(db):
    from ranker.explain import keep_matching_pages

    ranked = rank("web index", k=None, connection=db)            # pages 1, 2 and 3 all score
    assert {page_id for page_id, _ in ranked} == {1, 2, 3}
    with db.cursor() as cur:
        assert [p for p, _ in keep_matching_pages(cur, ranked, "web index")] == [2]


def test_a_word_missing_from_the_collection_gives_no_results(db):
    from ranker.explain import keep_matching_pages

    ranked = rank("web zebra", k=None, connection=db)            # rank() ignores "zebra"
    assert ranked
    with db.cursor() as cur:
        assert keep_matching_pages(cur, ranked, "web zebra") == []


def test_site_filter(db):
    from ranker.explain import keep_matching_pages

    ranked = rank("index", k=None, connection=db)
    with db.cursor() as cur:
        assert {p for p, _ in keep_matching_pages(cur, ranked, "index", "ir-book")} == {2, 3}
        assert keep_matching_pages(cur, ranked, "index", "wikipedia") == []


def test_explain_gives_the_same_score_as_rank(db):
    from ranker.explain import explain

    scores = dict(rank("web crawler", k=None, connection=db))
    with db.cursor() as cur:
        details = explain(cur, "web crawler", 1)
        assert details["cosine"] == pytest.approx(scores[1])
        assert details["title_bonus"] == 0 and details["score"] == details["cosine"]   # title "Page 1"
        assert details["score"] == pytest.approx(0.960416, abs=1e-6)       # hand calculation in test_rank.py
        assert {row["term"]: row["page_tf"] for row in details["terms"]} == {"web": 2, "crawler": 1}
        assert details["all_terms_present"]
        assert explain(cur, "web crawler", 999) is None


def test_title_bonus_lifts_a_page_about_the_query(db):
    from ranker.explain import TITLE_BONUS, boost_titles, explain

    with db.cursor() as cur:
        cur.execute("UPDATE pages SET title = 'Web index basics' WHERE id = 2")
        boosted = boost_titles(cur, [(1, 0.50), (2, 0.45)], "web")   # cosine scores: page 1 ahead
        assert boosted == [(2, pytest.approx(0.45 + TITLE_BONUS)), (1, 0.50)]   # "web" in page 2's title
        details = explain(cur, "web", 2)
        assert details["title_terms"] == ["web"]
        assert details["score"] == pytest.approx(details["cosine"] + TITLE_BONUS)
        assert details["cosine"] == pytest.approx(dict(rank("web", k=None, connection=db))[2])


def test_title_share_counts_distinct_query_words():
    from collections import Counter

    from ranker.explain import title_share

    assert title_share(Counter(["tolga", "yirtici"]), "Assoc. Prof. Dr. Tolga YIRTICI | CIU") == 1.0
    assert title_share(Counter(["tolga", "kamil"]), "Kamil Yurtkan") == 0.5
    assert title_share(Counter(), "anything") == 0.0


# ------------------------------------------------------------------ web routes (no database needed)
RECORDS = [
    {"id": 1, "title": "A", "url": "https://a.test", "snippet": "a", "score": 0.9, "site": "wikipedia"},
    {"id": 2, "title": "B", "url": "https://b.test", "snippet": "b", "score": 0.5, "site": "ir-book"},
]


def test_api_site_filter(monkeypatch):
    monkeypatch.setitem(app.config, "SEARCH_PROVIDER", lambda query: RECORDS)
    client = app.test_client()
    assert client.get("/search?q=x&site=ir-book").get_json()["total"] == 1
    assert client.get("/search?q=x&site=not-a-site").get_json()["total"] == 2      # unknown site is ignored


def test_results_page_shows_site_menu_and_details(monkeypatch):
    monkeypatch.setitem(app.config, "SEARCH_PROVIDER", lambda query: RECORDS)
    page = app.test_client().get("/results?q=x&site=wikipedia").get_data(as_text=True)
    assert '<option value="wikipedia" selected>' in page
    assert "Only in <b>Wikipedia</b>" in page
    assert "Rank <b>1</b>" in page and "How was this ranked?" in page


def test_explain_needs_a_query_and_a_page():
    assert app.test_client().get("/explain?q=web").status_code == 400
