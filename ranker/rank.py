import math
import os
from collections import Counter
from contextlib import closing

from dotenv import load_dotenv

from preprocessing.preprocess import preprocess


def rank(query, k=10, *, connection=None):
    """Return the highest-scoring (page_id, cosine score) pairs for a query."""
    if k is not None and k <= 0:
        return []

    query_frequencies = Counter(preprocess(query))
    if not query_frequencies:
        return []

    if connection is None:
        load_dotenv()
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL is not configured")

        import psycopg2

        with closing(psycopg2.connect(database_url)) as database_connection:
            return _rank_with_connection(query_frequencies, k, database_connection)

    return _rank_with_connection(query_frequencies, k, connection)


def _rank_with_connection(query_frequencies, k, connection):
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM pages")
        document_count = cursor.fetchone()[0]
        if not document_count:
            return []

        cursor.execute(
            "SELECT id, term, doc_freq FROM terms WHERE term = ANY(%s)",
            (list(query_frequencies),),
        )
        term_weights = {
            term_id: (math.log(document_count / document_frequency), query_frequencies[term])
            for term_id, term, document_frequency in cursor.fetchall()
            if document_frequency > 0
        }

        if not term_weights:
            return []

        term_ids = list(term_weights)
        idfs = [term_weights[term_id][0] for term_id in term_ids]
        query_tfs = [term_weights[term_id][1] for term_id in term_ids]
        query_norm = math.sqrt(
            sum((idf * query_tf) ** 2 for idf, query_tf in zip(idfs, query_tfs))
        )
        if query_norm == 0:
            return []

        sql = """
            WITH query_terms AS (
                SELECT *
                FROM unnest(
                    %s::INTEGER[],
                    %s::DOUBLE PRECISION[],
                    %s::INTEGER[]
                ) AS q(term_id, idf, query_tf)
            ),
            scores AS (
                SELECT p.page_id,
                       SUM(p.tf * q.idf * q.idf * q.query_tf) AS dot_product
                FROM query_terms AS q
                JOIN postings AS p ON p.term_id = q.term_id
                GROUP BY p.page_id
            )
            SELECT s.page_id, s.dot_product / (n.norm * %s) AS score
            FROM scores AS s
            JOIN page_norms AS n ON n.page_id = s.page_id
            WHERE n.norm > 0
            ORDER BY score DESC, s.page_id
        """
        parameters = [term_ids, idfs, query_tfs, query_norm]
        if k is not None:
            sql += " LIMIT %s"
            parameters.append(k)
        cursor.execute(sql, parameters)
        return [(page_id, float(score)) for page_id, score in cursor.fetchall()]
