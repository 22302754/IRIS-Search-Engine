import math

from indexer.build import _prepare_index, _read_pages
from preprocessing.preprocess import preprocess


def test_preprocess_contract_example():
    assert preprocess("The Crawlers are RUNNING fast!") == ["crawler", "run", "fast"]


def test_preprocess_removes_stop_words_punctuation_and_numbers():
    assert preprocess("A 123, database-index!") == ["databas", "index"]


def test_preprocess_returns_empty_for_empty_or_stop_word_text():
    assert preprocess("") == []
    assert preprocess("the and are") == []


def test_prepare_index_calculates_term_frequencies_and_document_frequencies():
    term_frequencies, document_frequencies, norms = _prepare_index(
        [(1, "red red blue"), (2, "blue green"), (3, "")]
    )

    assert term_frequencies[1] == {"red": 2, "blue": 1}
    assert term_frequencies[2] == {"blue": 1, "green": 1}
    assert term_frequencies[3] == {}
    assert document_frequencies == {"red": 1, "blue": 2, "green": 1}
    assert norms[1] == math.sqrt((2 * math.log(3)) ** 2 + math.log(1.5) ** 2)
    assert norms[2] == math.sqrt(math.log(1.5) ** 2 + math.log(3) ** 2)
    assert norms[3] == 0


def test_prepare_index_handles_no_documents():
    term_frequencies, document_frequencies, norms = _prepare_index([])

    assert term_frequencies == {}
    assert document_frequencies == {}
    assert norms == {}


def test_read_pages_fetches_small_keyset_batches():
    class Cursor:
        def __init__(self):
            self.rows = [(1, "first"), (3, "second"), (7, "third")]
            self.queries = []
            self.current = []

        def execute(self, statement, params):
            self.queries.append((statement, params))
            last_id, size = params
            self.current = [row for row in self.rows if row[0] > last_id][:size]

        def fetchall(self):
            return self.current

    cursor = Cursor()

    assert _read_pages(cursor, batch_size=2) == cursor.rows
    assert [params[0] for _, params in cursor.queries] == [0, 3, 7]
    assert all("WHERE id > %s" in statement for statement, _ in cursor.queries)


def test_read_pages_uses_crawl_or_update_timestamp_for_incremental_builds():
    class Cursor:
        def __init__(self):
            self.rows = [(2, "first"), (5, "second")]
            self.queries = []
            self.current = []

        def execute(self, statement, params):
            self.queries.append((statement, params))
            last_id, after, before, size = params
            assert after == "last-build"
            assert before == "build-start"
            self.current = [row for row in self.rows if row[0] > last_id][:size]

        def fetchall(self):
            return self.current

    cursor = Cursor()

    assert _read_pages(
        cursor,
        updated_after="last-build",
        updated_before="build-start",
        batch_size=1,
    ) == cursor.rows
    assert all("COALESCE(updated_at, crawled_at) > %s" in sql for sql, _ in cursor.queries)
    assert all("COALESCE(updated_at, crawled_at) <= %s" in sql for sql, _ in cursor.queries)


def test_fetch_pages_retries_a_dropped_connection(monkeypatch):
    import psycopg2

    import indexer.build as build

    class FakeConnection:
        closed = False
        autocommit = False

        def cursor(self):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def close(self):
            self.closed = True

    pages = [(i, f"text {i}") for i in range(1, 8)]
    calls = {"n": 0}

    def fake_read(cursor, *, start_after=0, batch_size=50, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:                                   # the second batch loses its connection
            raise psycopg2.OperationalError("server closed the connection unexpectedly")
        return [p for p in pages if p[0] > start_after][:batch_size]

    monkeypatch.setattr(build, "_connect", lambda url: FakeConnection())
    monkeypatch.setattr(build, "_read_pages", fake_read)
    monkeypatch.setattr(build.time, "sleep", lambda seconds: None)
    assert build._fetch_pages("postgresql://test", batch_size=3, log=lambda msg: None) == pages
