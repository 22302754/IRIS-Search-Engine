"""
The search page's ranking in two database round trips (instead of about nine).

    from ranker.search import search_page
    total, results = search_page(connection, "inverted index", page=1, per_page=10, site=None)

It gives exactly the scores of rank() (TF-IDF weights, cosine similarity), keeps only the pages that contain
every query word (and are on `site`), adds the title bonus of ranker.explain, and returns the requested page of
results with the data the results page shows. rank() itself is unchanged and is still the reference: the tests
check that both give the same cosine scores.

Why it is faster: the old path called rank() for every matching page (3 queries), then filtered (3 queries),
boosted titles (1), read the result pages (1) and their query words (1) - nine trips to a cloud database about
70 ms away - and downloaded the full text of the 10 result pages just to cut a 30-word snippet from it.
"""
from ranker.explain import TITLE_BONUS, query_terms, title_share

SNIPPET_WINDOW = 1500      # characters of page text sent for each result's snippet
SNIPPET_LEAD = 400         # of which this many come before the first query word

_SCORES_SQL = """
WITH q(term, qtf) AS (SELECT * FROM unnest(%(terms)s::text[], %(qtfs)s::int[])),
     n AS (SELECT count(*)::float8 AS n FROM pages),
     qt AS (SELECT t.id, q.qtf, ln(n.n / t.doc_freq) AS idf
            FROM q JOIN terms AS t ON t.term = q.term CROSS JOIN n
            WHERE t.doc_freq > 0),
     qn AS (SELECT sqrt(sum((qtf * idf) ^ 2)) AS norm, count(*) AS known FROM qt),
     sc AS (SELECT p.page_id, sum(p.tf * qt.idf * qt.idf * qt.qtf) AS dot, count(*) AS hits
            FROM qt JOIN postings AS p ON p.term_id = qt.id
            GROUP BY p.page_id)
SELECT sc.page_id, sc.dot / (pn.norm * qn.norm) AS cosine, pg.title
FROM sc
JOIN page_norms AS pn ON pn.page_id = sc.page_id
JOIN pages AS pg ON pg.id = sc.page_id
CROSS JOIN qn
WHERE pn.norm > 0 AND qn.norm > 0
  AND qn.known = %(n_terms)s            -- every query word is in the index ...
  AND sc.hits = %(n_terms)s             -- ... and in this page
  AND (%(site)s::text IS NULL OR pg.site = %(site)s::text)
"""

_DETAILS_SQL = """
SELECT pg.id, pg.title, pg.url, pg.description, pg.site,
       substring(pg.text FROM greatest(coalesce(w.pos, 1) - %(lead)s, 1) FOR %(window)s) AS part,
       greatest(coalesce(w.pos, 1) - %(lead)s, 1) AS part_start,
       (SELECT json_object_agg(t.term, p.tf)
          FROM postings AS p JOIN terms AS t ON t.id = p.term_id
         WHERE p.page_id = pg.id AND t.term = ANY(%(terms)s)) AS matched
FROM pages AS pg
CROSS JOIN LATERAL (SELECT min(nullif(strpos(lower(pg.text), s), 0)) AS pos
                      FROM unnest(%(terms)s::text[]) AS s) AS w
WHERE pg.id = ANY(%(ids)s)
"""


def search_page(connection, query, page=1, per_page=10, site=None):
    """(total, [result dicts]) for one page of results, best first."""
    terms = query_terms(query)
    if not terms:
        return 0, []
    with connection.cursor() as cursor:
        cursor.execute(_SCORES_SQL, {"terms": list(terms), "qtfs": list(terms.values()),
                                     "n_terms": len(terms), "site": site or None})
        scored = [(page_id, cosine + TITLE_BONUS * title_share(terms, title), cosine)
                  for page_id, cosine, title in cursor.fetchall()]
        scored.sort(key=lambda row: (-row[1], row[0]))
        total = len(scored)
        start = (max(page, 1) - 1) * per_page
        chosen = scored[start:start + per_page]
        if not chosen:
            return total, []

        cursor.execute(_DETAILS_SQL, {"terms": list(terms), "ids": [row[0] for row in chosen],
                                      "lead": SNIPPET_LEAD, "window": SNIPPET_WINDOW})
        details = {row[0]: row for row in cursor.fetchall()}

    results = []
    for page_id, score, cosine in chosen:
        if page_id not in details:
            continue
        _, title, url, description, page_site, part, part_start, matched = details[page_id]
        results.append({"id": page_id, "title": title or url, "url": url, "description": description,
                        "text_part": part or "", "part_is_cut": part_start > 1, "site": page_site,
                        "matched_terms": dict(sorted((matched or {}).items())), "score": float(score),
                        "cosine": float(cosine)})
    return total, results
