"""
Ranking details for the web page: which pages really contain the query, and why a page got its score.

    from ranker.explain import query_terms, keep_matching_pages, matched_terms, explain

rank() scores every page that contains at least one query word. The search page is stricter:
  * a page is shown only when it contains EVERY query word (after pre-processing);
  * a query word that is not in the index at all means the collection has nothing on it -> no results;
  * results can be limited to one site.

explain() repeats the TF-IDF / cosine calculation of rank() for one page, word by word, so the numbers
can be shown and checked:  score = sum(w_q * w_d) / (|q| * |d|),  w = tf * ln(N / df).
"""
import math
from collections import Counter

from preprocessing.preprocess import preprocess


def query_terms(query):
    """Query words as the index stores them, with how often each occurs in the query."""
    return Counter(preprocess(query or ""))


def term_stats(cursor, terms):
    """{term: (term_id, doc_freq)} for the query words found in the index, and N (number of pages)."""
    if not terms:
        return {}, 0
    cursor.execute("SELECT term, id, doc_freq FROM terms WHERE term = ANY(%s)", (list(terms),))
    stats = {term: (term_id, df) for term, term_id, df in cursor.fetchall()}
    cursor.execute("SELECT COUNT(*) FROM pages")
    return stats, cursor.fetchone()[0]


def keep_matching_pages(cursor, ranked, query, site=None):
    """The ranked (page_id, score) pairs whose page contains every query word (and is on `site`)."""
    terms = query_terms(query)
    stats, _ = term_stats(cursor, terms)
    if not terms or len(stats) < len(terms) or not ranked:
        return []                                   # a query word is not in the collection at all
    page_ids = [page_id for page_id, _ in ranked]
    sql = ("SELECT p.page_id FROM postings AS p JOIN pages AS pg ON pg.id = p.page_id "
           "WHERE p.term_id = ANY(%s) AND p.page_id = ANY(%s)")
    params = [[term_id for term_id, _ in stats.values()], page_ids]
    if site:
        sql += " AND pg.site = %s"
        params.append(site)
    sql += " GROUP BY p.page_id HAVING COUNT(*) = %s"
    params.append(len(stats))
    cursor.execute(sql, params)
    keep = {row[0] for row in cursor.fetchall()}
    return [(page_id, score) for page_id, score in ranked if page_id in keep]


def matched_terms(cursor, query, page_ids):
    """{page_id: {term: tf}} for the query words in each of the given pages."""
    terms = query_terms(query)
    if not terms or not page_ids:
        return {}
    cursor.execute(
        "SELECT p.page_id, t.term, p.tf FROM postings AS p JOIN terms AS t ON t.id = p.term_id "
        "WHERE t.term = ANY(%s) AND p.page_id = ANY(%s)",
        (list(terms), list(page_ids)),
    )
    found = {}
    for page_id, term, tf in cursor.fetchall():
        found.setdefault(page_id, {})[term] = tf
    return found


def explain(cursor, query, page_id):
    """Every number behind the score of one page for one query (None if the page does not exist)."""
    cursor.execute("SELECT id, title, url, site, word_count FROM pages WHERE id = %s", (page_id,))
    page = cursor.fetchone()
    if page is None:
        return None
    terms = query_terms(query)
    stats, n_pages = term_stats(cursor, terms)
    tf_in_page = matched_terms(cursor, query, [page_id]).get(page_id, {})
    cursor.execute("SELECT norm FROM page_norms WHERE page_id = %s", (page_id,))
    row = cursor.fetchone()
    page_norm = row[0] if row else 0.0

    rows = []
    for term, query_tf in terms.items():
        if term not in stats:
            rows.append({"term": term, "in_index": False, "df": 0, "idf": 0.0, "query_tf": query_tf,
                         "query_weight": 0.0, "page_tf": 0, "page_weight": 0.0, "product": 0.0})
            continue
        df = stats[term][1]
        idf = math.log(n_pages / df) if df else 0.0
        page_tf = tf_in_page.get(term, 0)
        rows.append({"term": term, "in_index": True, "df": df, "idf": idf, "query_tf": query_tf,
                     "query_weight": query_tf * idf, "page_tf": page_tf, "page_weight": page_tf * idf,
                     "product": query_tf * idf * page_tf * idf})

    dot = sum(r["product"] for r in rows)
    query_norm = math.sqrt(sum(r["query_weight"] ** 2 for r in rows))
    score = dot / (query_norm * page_norm) if query_norm and page_norm else 0.0
    return {
        "page": {"id": page[0], "title": page[1] or page[2], "url": page[2], "site": page[3], "words": page[4]},
        "n_pages": n_pages, "terms": rows, "dot": dot, "query_norm": query_norm, "page_norm": page_norm,
        "score": score, "all_terms_present": all(r["page_tf"] > 0 for r in rows) and bool(rows),
    }
