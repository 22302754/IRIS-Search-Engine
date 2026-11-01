import argparse
import math
import os
from collections import Counter, defaultdict
from contextlib import closing

from dotenv import load_dotenv
from psycopg2.extras import execute_values

from preprocessing.preprocess import preprocess

_BATCH_SIZE = 1000
_PAGE_FETCH_SIZE = 100


def _read_pages(cursor, *, updated_after=None, updated_before=None,
                batch_size=_PAGE_FETCH_SIZE):
    """Read pages in small keyset-paginated batches.

    An incremental query uses ``COALESCE(updated_at, crawled_at)`` so a newly
    crawled page with no later update is never skipped.
    """
    documents = []
    last_id = 0
    while True:
        conditions = ["id > %s"]
        parameters = [last_id]
        if updated_after is not None:
            conditions.append("COALESCE(updated_at, crawled_at) > %s")
            parameters.append(updated_after)
        if updated_before is not None:
            conditions.append("COALESCE(updated_at, crawled_at) <= %s")
            parameters.append(updated_before)
        parameters.append(batch_size)
        cursor.execute(
            "SELECT id, text FROM pages WHERE "
            + " AND ".join(conditions)
            + " ORDER BY id LIMIT %s",
            parameters,
        )
        rows = cursor.fetchall()
        if not rows:
            return documents
        documents.extend(rows)
        last_id = rows[-1][0]


def _prepare_index(documents):
    """Return term frequencies, document frequencies, and TF-IDF vector norms."""
    documents = list(documents)
    document_count = len(documents)
    term_frequencies = {}
    document_frequencies = Counter()

    for page_id, text in documents:
        frequencies = Counter(preprocess(text or ""))
        term_frequencies[page_id] = frequencies
        document_frequencies.update(frequencies.keys())

    norms = {}
    if document_count:
        for page_id, frequencies in term_frequencies.items():
            squared_norm = sum(
                (frequency * math.log(document_count / document_frequencies[term])) ** 2
                for term, frequency in frequencies.items()
            )
            norms[page_id] = math.sqrt(squared_norm)
    else:
        norms = {}

    return term_frequencies, document_frequencies, norms


def _ensure_schema(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS terms (
            id SERIAL PRIMARY KEY,
            term TEXT NOT NULL UNIQUE,
            doc_freq INTEGER NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS postings (
            term_id INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
            page_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
            tf INTEGER NOT NULL,
            PRIMARY KEY (term_id, page_id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS page_norms (
            page_id INTEGER PRIMARY KEY REFERENCES pages(id) ON DELETE CASCADE,
            norm DOUBLE PRECISION NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS index_state (
            singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
            last_indexed_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS postings_term_id_idx ON postings (term_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS postings_page_id_idx ON postings (page_id)")


def _insert_postings(cursor, term_frequencies, term_ids):
    """Write posting rows in bounded batches."""
    posting_rows = (
        (term_ids[term], page_id, frequency)
        for page_id, frequencies in term_frequencies.items()
        for term, frequency in frequencies.items()
    )
    batch = []
    for posting in posting_rows:
        batch.append(posting)
        if len(batch) == _BATCH_SIZE:
            execute_values(
                cursor,
                "INSERT INTO postings (term_id, page_id, tf) VALUES %s",
                batch,
                page_size=_BATCH_SIZE,
            )
            batch.clear()
    if batch:
        execute_values(
            cursor,
            "INSERT INTO postings (term_id, page_id, tf) VALUES %s",
            batch,
            page_size=_BATCH_SIZE,
        )


def _remove_orphaned_index_rows(cursor):
    """Remove references left behind by a page deleted outside the FK path."""
    cursor.execute(
        "DELETE FROM page_norms AS n WHERE NOT EXISTS "
        "(SELECT 1 FROM pages AS p WHERE p.id = n.page_id)"
    )
    removed_norms = cursor.rowcount
    cursor.execute(
        "DELETE FROM postings AS posting WHERE NOT EXISTS "
        "(SELECT 1 FROM pages AS p WHERE p.id = posting.page_id)"
    )
    return removed_norms, cursor.rowcount


def _replace_changed_pages(cursor, documents):
    """Replace postings only for pages changed since the last checkpoint."""
    if not documents:
        return

    page_ids = [page_id for page_id, _ in documents]
    cursor.execute("DELETE FROM postings WHERE page_id = ANY(%s)", (page_ids,))
    term_frequencies, document_frequencies, _ = _prepare_index(documents)
    if not document_frequencies:
        return

    execute_values(
        cursor,
        "INSERT INTO terms (term, doc_freq) VALUES %s ON CONFLICT (term) DO NOTHING",
        [(term, 0) for term in sorted(document_frequencies)],
        page_size=_BATCH_SIZE,
    )
    cursor.execute(
        "SELECT id, term FROM terms WHERE term = ANY(%s)",
        (list(document_frequencies),),
    )
    term_ids = {term: term_id for term_id, term in cursor.fetchall()}
    _insert_postings(cursor, term_frequencies, term_ids)


def _refresh_document_frequencies_and_norms(cursor):
    """Refresh global TF-IDF values after an incremental posting change."""
    cursor.execute(
        "DELETE FROM terms AS t WHERE NOT EXISTS "
        "(SELECT 1 FROM postings AS p WHERE p.term_id = t.id)"
    )
    cursor.execute(
        """
        UPDATE terms AS t
        SET doc_freq = counts.doc_freq
        FROM (
            SELECT term_id, COUNT(*)::INTEGER AS doc_freq
            FROM postings
            GROUP BY term_id
        ) AS counts
        WHERE t.id = counts.term_id
        """
    )
    cursor.execute("SELECT COUNT(*) FROM pages")
    document_count = cursor.fetchone()[0]
    cursor.execute("TRUNCATE TABLE page_norms")
    if document_count:
        cursor.execute(
            """
            INSERT INTO page_norms (page_id, norm)
            SELECT p.id,
                   COALESCE(SQRT(SUM(POWER(
                       posting.tf * LN(%s::DOUBLE PRECISION / term.doc_freq), 2
                   ))), 0)
            FROM pages AS p
            LEFT JOIN postings AS posting ON posting.page_id = p.id
            LEFT JOIN terms AS term ON term.id = posting.term_id
            GROUP BY p.id
            """,
            (document_count,),
        )


def _get_last_indexed_at(cursor):
    cursor.execute("SELECT last_indexed_at FROM index_state WHERE singleton = TRUE")
    row = cursor.fetchone()
    return row[0] if row else None


def _record_build(cursor, completed_at):
    cursor.execute(
        """
        INSERT INTO index_state (singleton, last_indexed_at)
        VALUES (TRUE, %s)
        ON CONFLICT (singleton)
        DO UPDATE SET last_indexed_at = EXCLUDED.last_indexed_at
        """,
        (completed_at,),
    )


def _index_statistics(cursor):
    cursor.execute("SELECT COUNT(*) FROM pages")
    document_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM terms")
    term_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM postings")
    posting_count = cursor.fetchone()[0]
    return {"documents": document_count, "terms": term_count, "postings": posting_count}


def build_index(database_url=None, *, force_full=False):
    """Build once, then update only pages changed since the last build.

    A checkpoint is stored in ``index_state`` only after the transaction
    completes. Document frequencies and every page norm are refreshed whenever
    changed or deleted pages alter the global TF-IDF collection statistics.
    """
    load_dotenv()
    database_url = database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    import psycopg2

    with closing(psycopg2.connect(database_url)) as connection:
        with connection:
            with connection.cursor() as cursor:
                _ensure_schema(cursor)
                cursor.execute("SELECT CURRENT_TIMESTAMP")
                build_started_at = cursor.fetchone()[0]
                last_indexed_at = _get_last_indexed_at(cursor)

                if force_full or last_indexed_at is None:
                    documents = _read_pages(cursor)
                    term_frequencies, document_frequencies, norms = _prepare_index(documents)
                    cursor.execute("TRUNCATE TABLE page_norms, terms RESTART IDENTITY CASCADE")

                    if document_frequencies:
                        term_rows = [
                            (term, document_frequencies[term])
                            for term in sorted(document_frequencies)
                        ]
                        inserted_terms = execute_values(
                            cursor,
                            """
                            INSERT INTO terms (term, doc_freq)
                            VALUES %s
                            RETURNING id, term
                            """,
                            term_rows,
                            page_size=_BATCH_SIZE,
                            fetch=True,
                        )
                        term_ids = {term: term_id for term_id, term in inserted_terms}
                        _insert_postings(cursor, term_frequencies, term_ids)

                    if norms:
                        execute_values(
                            cursor,
                            "INSERT INTO page_norms (page_id, norm) VALUES %s",
                            list(norms.items()),
                            page_size=_BATCH_SIZE,
                        )
                    result = {
                        "documents": len(documents),
                        "terms": len(document_frequencies),
                        "postings": sum(
                            len(frequencies) for frequencies in term_frequencies.values()
                        ),
                        "mode": "full",
                        "changed_pages": len(documents),
                    }
                else:
                    changed_documents = _read_pages(
                        cursor,
                        updated_after=last_indexed_at,
                        updated_before=build_started_at,
                    )
                    _remove_orphaned_index_rows(cursor)
                    if changed_documents:
                        _replace_changed_pages(cursor, changed_documents)
                    # Page deletes cascade to postings. Refresh the global
                    # statistics every incremental run so deletes cannot leave
                    # stale df values or cosine norms behind.
                    _refresh_document_frequencies_and_norms(cursor)
                    result = _index_statistics(cursor)
                    result.update(
                        {"mode": "incremental", "changed_pages": len(changed_documents)}
                    )

                _record_build(cursor, build_started_at)
                return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build or incrementally update the IRIS index.")
    parser.add_argument(
        "--full",
        action="store_true",
        help="ignore the checkpoint and rebuild all index tables",
    )
    args = parser.parse_args(argv)
    result = build_index(force_full=args.full)
    print(
        "{mode} index: {documents} pages, {terms} terms, {postings} postings "
        "({changed_pages} changed pages).".format(**result)
    )


if __name__ == "__main__":
    main()
