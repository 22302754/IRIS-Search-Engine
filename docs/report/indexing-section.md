# Indexing and Search API

## Index construction

IRIS stores crawled pages in PostgreSQL and builds an inverted index in the
`terms`, `postings`, and `page_norms` tables. The indexer uses the shared
`preprocess(text)` function, so document tokens and query tokens use the same
lowercasing, stop-word removal, and Porter stemming rules.

For a collection of `N` pages, the indexer stores a document frequency `df(t)`
for each term and a term frequency `tf(t,d)` for each page. The ranker uses the
weight `tf(t,d) * log(N / df(t))` and cosine similarity. `page_norms` stores
the denominator for each document vector.

The first `python -m indexer.build` run creates the complete index in one
transaction. Later runs are incremental: they select pages whose
`COALESCE(updated_at, crawled_at)` is newer than the stored checkpoint, replace
only those pages' postings, remove references for deleted pages, and then
refresh document frequencies and vector norms for the collection. The checkpoint
is advanced only after the transaction succeeds.

## Verified cloud build

On 1 November 2026, the shared Supabase database was indexed successfully:

| Measurement | Result |
| --- | ---: |
| Pages indexed | 3,769 |
| Unique terms | 85,640 |
| Postings | 1,201,490 |
| Full-build time | 921.4 seconds (15 min 21 sec) |

The JSON endpoint was verified with the query `information retrieval`: it
returned HTTP 200, 1,567 matching pages, and the first 10 results contained the
required `id`, `title`, `url`, `snippet`, and `score` fields. Its measured
response time in that verification was 3,183 ms.

## Search API

`GET /search?q=<query>&page=<page>` validates that `q` is not empty, delegates
ranking to `ranker.rank`, retrieves the selected pages, and returns the agreed
JSON contract: `query`, `total`, `page`, `per_page`, `time_ms`, and `results`.
Each result contains `id`, `title`, `url`, `snippet`, and `score`.

The project does not yet contain the team-owned `docs/test-queries.md` file, so
the required 20-query response-time table cannot be recorded without inventing
the team's evaluation queries. Once that file is supplied, run the listed
queries against `/search` and add their `time_ms` values here.
