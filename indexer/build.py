import math
import os
from collections import Counter, defaultdict
from contextlib import closing

from dotenv import load_dotenv
from psycopg2.extras import execute_values

from preprocessing.preprocess import preprocess

_BATCH_SIZE = 1000


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


def build_index(database_url=None):
    """Atomically rebuild the search index from all rows in the pages table."""
    load_dotenv()
    database_url = database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    import psycopg2

    with closing(psycopg2.connect(database_url)) as connection:
        with connection:
            with connection.cursor() as cursor:
                _ensure_schema(cursor)
                cursor.execute("SELECT id, text FROM pages ORDER BY id")
                documents = cursor.fetchall()

                term_frequencies, document_frequencies, norms = _prepare_index(documents)
                document_count = len(documents)

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

                if norms:
                    execute_values(
                        cursor,
                        "INSERT INTO page_norms (page_id, norm) VALUES %s",
                        list(norms.items()),
                        page_size=_BATCH_SIZE,
                    )

        return {
            "documents": document_count,
            "terms": len(document_frequencies),
            "postings": sum(len(frequencies) for frequencies in term_frequencies.values()),
        }


def main():
    result = build_index()
    print(
        "Indexed {documents} pages: {terms} terms and {postings} postings.".format(
            **result
        )
    )


if __name__ == "__main__":
    main()
