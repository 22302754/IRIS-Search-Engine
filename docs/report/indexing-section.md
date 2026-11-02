# Indexing and Search API

## Index construction

IRIS stores crawled pages in PostgreSQL and builds an inverted index in the
`terms`, `postings`, and `page_norms` tables. The indexer uses the shared
`preprocess(text)` function, so document tokens and query tokens use the same
lowercasing, folding of accented and Turkish letters, stop-word removal, and
Porter stemming rules.

For a collection of `N` pages, the indexer stores a document frequency `df(t)`
for each term and a term frequency `tf(t,d)` for each page. The ranker uses the
weight `tf(t,d) * log(N / df(t))` and cosine similarity. `page_norms` stores
the denominator for each document vector.

The first `python -m indexer.build` run creates the complete index; later runs are
incremental: they select pages whose `COALESCE(updated_at, crawled_at)` is newer
than the stored checkpoint in `index_state`, replace only those pages' postings,
remove references for deleted pages, and then refresh document frequencies and
vector norms for the collection. `python -m indexer.build --full` rebuilds
everything, which is needed when `preprocess()` changes. The checkpoint is
advanced only after the write transaction succeeds.

### Building over an unreliable connection

The shared database is in the cloud, so a build depends on a long network
connection. A full build on 2 November failed when that connection was cut while
the indexer was still reading pages. The indexer was therefore split into three
steps:

1. A short transaction records the start time and the last checkpoint.
2. The pages are read in batches of 50 over short connections with TCP
   keep-alives. If a connection drops, the indexer reconnects and continues from
   the last page it received (up to four attempts per batch).
3. One write transaction replaces the index, so searches see either the old or
   the new index, never a half-built one. The 1.46 million postings are loaded
   with PostgreSQL `COPY` instead of row-by-row `INSERT` statements, and the
   tables are vacuumed and analysed afterwards so the planner has fresh
   statistics.

### Database indexes

| Index | Used for |
| --- | --- |
| `terms(term)` (unique) | Finding the query terms |
| `postings(term_id) INCLUDE (page_id, tf)` | Reading a term's postings from the index alone (index-only scan) |
| `postings(page_id)` | Replacing the postings of a changed page in incremental builds |
| `page_norms(page_id)` (primary key) | The cosine denominator of each page |

With the covering index the scoring query for *information retrieval* (911
matching pages) fell from 431 ms to 40 ms on a cold cache, and the 20 test
queries now take under 5 ms each in the database (see the ranking section).

## Index statistics

| Measurement | 1 November 2026 | 2 November 2026 |
| --- | ---: | ---: |
| Pages indexed | 3,769 | 4,697 |
| Sites | 9 | 10 (CIU website added) |
| Unique terms | 85,640 | 102,128 |
| Postings | 1,201,490 | 1,458,705 |
| Full-build time | 921.4 s (row inserts) | **[…] s** (`COPY`) |

The number of terms grew faster than the number of pages because the CIU pages
contain many names and Turkish words that appear nowhere else.

## Search API

`GET /search?q=<query>&page=<page>[&site=<site>]` validates that `q` is not empty
(HTTP 400 otherwise) and returns the agreed JSON contract: `query`, `total`,
`page`, `per_page`, `time_ms`, and `results`, where each result has `id`, `title`,
`url`, `snippet`, and `score`, plus `site` and `matched_terms`. Only pages that
contain every query word are returned, with the title bonus described in the
ranking section.

The first version of the route made about nine round trips to the database per
search (three in `rank()`, then filtering, the title bonus, the page details and
the matched words) and downloaded the full text of the ten result pages to cut a
30-word snippet. From Cyprus each round trip to the database in Frankfurt takes
about 70 ms. The route now uses `ranker/search.py`, which needs **two** round
trips: one query scores, filters and returns the titles of all matching pages;
a second query returns only the ten pages shown, with a 1,500-character window of
text around the first query word and the query words found in each page. The
scores are identical to those of `rank()`, which the tests check. Database
connections are kept open in a small pool between searches.

| Measurement | Value |
| --- | ---: |
| Database round trips per search | 9 → 2 |
| Page text sent per search | full text of 10 pages → at most 15,000 characters |
| Database time, 20 test queries | 1.1–2.9 ms each |
| Response time on the laptop, 20 test queries (median) | **[…] ms** |
| Response time on the public site, 20 test queries (median) | **[…] ms** |

The last two rows are measured with
`python3 -m infra.smoke_test --base-url <url> --out docs/smoke-test.md`, which
sends the 20 queries of `docs/test-queries.json` and records the time of each.
