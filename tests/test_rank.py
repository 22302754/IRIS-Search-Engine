"""Tests for rank() in ranker/rank.py: a hand-calculated example, plus empty and unknown queries.

Every test runs twice:
  * "memory"   - an in-memory stand-in for the database (always runs, also in CI);
  * "postgres" - the real SQL in rank() on PostgreSQL, only when IRIS_TEST_DATABASE_URL is set,
                 e.g. IRIS_TEST_DATABASE_URL=postgresql://postgres@localhost:5432/postgres
                 The tables are TEMPORARY tables that exist only inside the test's connection and
                 hide any real tables of the same name, so the real index is never read or changed.
                 Still, prefer a local test database over the shared one.

Hand-calculated example (weights as in the indexer: w = tf * ln(N / df), score = cosine)
---------------------------------------------------------------------------------------
    page 1: "web crawler web"   -> web:2  crawler:1
    page 2: "web index"         -> web:1  index:1
    page 3: "index rank rank"   -> index:1  rank:2

    N = 3 pages.  df: web 2, index 2, crawler 1, rank 1
    idf(web) = idf(index) = ln(3/2) = a = 0.405465
    idf(crawler) = idf(rank) = ln(3/1) = b = 1.098612

    |page 1| = sqrt((2a)^2 + b^2) = 1.365488
    |page 2| = sqrt(a^2 + a^2)    = 0.573414
    |page 3| = sqrt(a^2 + (2b)^2) = 2.234323

    Query "web crawler":   q = (web: a, crawler: b),  |q| = sqrt(a^2 + b^2) = 1.171047
        page 1: (2a*a + b*b) / (1.365488 * 1.171047) = 1.535753 / 1.599050 = 0.960416
        page 2: (a*a)        / (0.573414 * 1.171047) = 0.164402 / 0.671495 = 0.244830
        page 3: no query word -> not returned
        order: 1, 2

    Query "ranking index": "ranking" is stemmed to "rank"; q = (rank: b, index: a), |q| = 1.171047
        page 3: (2b*b + a*a) / (2.234323 * 1.171047) = 2.578300 / 2.616497 = 0.985402
        page 2: (a*a)        / (0.573414 * 1.171047) = 0.244830
        order: 3, 2
"""
import math
import os

import pytest

from indexer.build import _prepare_index
from ranker.rank import rank

DOCS = [(1, "web crawler web"), (2, "web index"), (3, "index rank rank")]

A = math.log(3 / 2)          # idf of web and index
B = math.log(3)              # idf of crawler and rank
NORM_1 = math.sqrt((2 * A) ** 2 + B ** 2)
NORM_2 = math.sqrt(A ** 2 + A ** 2)
NORM_3 = math.sqrt(A ** 2 + (2 * B) ** 2)
Q_NORM = math.sqrt(A ** 2 + B ** 2)


# ------------------------------------------------------------------ in-memory stand-in for the DB
class MemoryCursor:
    """Answers the three statements rank() sends, from tables built by the real indexer code."""

    def __init__(self, db):
        self.db = db
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.db.statements.append(sql)
        if "COUNT(*) FROM pages" in sql:
            self.rows = [(len(self.db.pages),)]
        elif "FROM terms WHERE term = ANY" in sql:
            wanted = set(params[0])
            self.rows = [(tid, term, df) for term, (tid, df) in self.db.terms.items() if term in wanted]
        elif "JOIN postings" in sql:
            # Same meaning as the SQL: sum tf * idf * idf * query_tf per page, divide by the two
            # norms, skip zero norms, order by score desc then page_id, optional LIMIT.
            term_ids, idfs, query_tfs, query_norm = params[:4]
            limit = params[4] if len(params) > 4 else None
            dots = {}
            for term_id, idf, query_tf in zip(term_ids, idfs, query_tfs):
                for page_id, tf in self.db.postings.get(term_id, []):
                    dots[page_id] = dots.get(page_id, 0.0) + tf * idf * idf * query_tf
            scored = [(pid, dot / (self.db.norms[pid] * query_norm))
                      for pid, dot in dots.items() if self.db.norms.get(pid, 0) > 0]
            scored.sort(key=lambda row: (-row[1], row[0]))
            self.rows = scored[:limit] if limit is not None else scored
        else:
            raise AssertionError(f"unexpected SQL: {sql}")

    def fetchone(self):
        return self.rows[0]

    def fetchall(self):
        return self.rows


class MemoryConnection:
    def __init__(self, docs):
        term_frequencies, document_frequencies, self.norms = _prepare_index(docs)
        self.pages = [pid for pid, _ in docs]
        self.terms = {term: (i, df) for i, (term, df) in enumerate(sorted(document_frequencies.items()), 1)}
        self.postings = {}
        for page_id, counts in term_frequencies.items():
            for term, tf in counts.items():
                self.postings.setdefault(self.terms[term][0], []).append((page_id, tf))
        self.statements = []

    def cursor(self):
        return MemoryCursor(self)


# ------------------------------------------------------------------ real PostgreSQL (optional)
def postgres_connection(docs):
    url = os.environ.get("IRIS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("set IRIS_TEST_DATABASE_URL to also run rank() on PostgreSQL")
    import psycopg2

    conn = psycopg2.connect(url)
    term_frequencies, document_frequencies, norms = _prepare_index(docs)
    with conn.cursor() as cur:
        cur.execute("CREATE TEMP TABLE pages (id INTEGER PRIMARY KEY, text TEXT)")
        cur.execute("CREATE TEMP TABLE terms (id SERIAL PRIMARY KEY, term TEXT UNIQUE, doc_freq INTEGER)")
        cur.execute("CREATE TEMP TABLE postings (term_id INTEGER, page_id INTEGER, tf INTEGER, "
                    "PRIMARY KEY (term_id, page_id))")
        cur.execute("CREATE TEMP TABLE page_norms (page_id INTEGER PRIMARY KEY, norm DOUBLE PRECISION)")
        cur.executemany("INSERT INTO pages VALUES (%s, %s)", docs)
        for term, df in sorted(document_frequencies.items()):
            cur.execute("INSERT INTO terms (term, doc_freq) VALUES (%s, %s) RETURNING id", (term, df))
            term_id = cur.fetchone()[0]
            cur.executemany("INSERT INTO postings VALUES (%s, %s, %s)",
                            [(term_id, pid, counts[term]) for pid, counts in term_frequencies.items()
                             if term in counts])
        cur.executemany("INSERT INTO page_norms VALUES (%s, %s)", list(norms.items()))
    return conn


@pytest.fixture(params=["memory", "postgres"])
def db(request):
    if request.param == "memory":
        yield MemoryConnection(DOCS)
    else:
        conn = postgres_connection(DOCS)
        yield conn
        conn.close()                # temporary tables disappear here


# ------------------------------------------------------------------ the hand-calculated example
def test_index_matches_the_hand_calculation():
    _, document_frequencies, norms = _prepare_index(DOCS)
    assert document_frequencies == {"web": 2, "crawler": 1, "index": 2, "rank": 1}
    assert norms[1] == pytest.approx(1.365488, abs=1e-6)
    assert norms[2] == pytest.approx(0.573414, abs=1e-6)
    assert norms[3] == pytest.approx(2.234323, abs=1e-6)


def test_query_web_crawler_exact_scores_and_order(db):
    results = rank("web crawler", connection=db)

    assert [page_id for page_id, _ in results] == [1, 2]          # page 3 has no query word
    assert results[0][1] == pytest.approx((2 * A * A + B * B) / (NORM_1 * Q_NORM))
    assert results[1][1] == pytest.approx((A * A) / (NORM_2 * Q_NORM))
    assert results[0][1] == pytest.approx(0.960416, abs=1e-6)     # the hand-worked values
    assert results[1][1] == pytest.approx(0.244830, abs=1e-6)


def test_query_ranking_index_exact_scores_and_order(db):
    results = rank("ranking index", connection=db)                # "ranking" -> "rank"

    assert [page_id for page_id, _ in results] == [3, 2]
    assert results[0][1] == pytest.approx((2 * B * B + A * A) / (NORM_3 * Q_NORM))
    assert results[1][1] == pytest.approx((A * A) / (NORM_2 * Q_NORM))
    assert results[0][1] == pytest.approx(0.985402, abs=1e-6)
    assert results[1][1] == pytest.approx(0.244830, abs=1e-6)


def test_results_follow_the_contract(db):
    results = rank("web crawler", connection=db)
    assert all(isinstance(pid, int) and isinstance(score, float) for pid, score in results)
    assert all(0 < score <= 1 for _, score in results)


def test_k_limits_the_number_of_results(db):
    assert rank("web crawler", k=1, connection=db) == rank("web crawler", connection=db)[:1]
    assert rank("web crawler", k=0, connection=db) == []


def test_identical_query_and_page_score_one(db):
    assert rank("web crawler web", connection=db)[0] == (1, pytest.approx(1.0))


# ------------------------------------------------------------------ unknown, empty, stop words
def test_unknown_word_returns_empty_list(db):
    assert rank("zebra", connection=db) == []


def test_unknown_words_are_ignored_next_to_known_ones(db):
    assert rank("web crawler zebra", connection=db) == rank("web crawler", connection=db)


@pytest.mark.parametrize("query", ["", "   ", "!!! ...", "2026", "the and of", "The AND of!"])
def test_empty_or_stop_word_only_query_returns_empty_list(db, query):
    assert rank(query, connection=db) == []


def test_empty_query_does_not_touch_the_database():
    conn = MemoryConnection(DOCS)
    assert rank("the and of", connection=conn) == []
    assert conn.statements == []


def test_unknown_word_skips_the_scoring_query():
    conn = MemoryConnection(DOCS)
    assert rank("zebra", connection=conn) == []
    assert not any("JOIN postings" in sql for sql in conn.statements)
