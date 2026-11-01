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
required `id`, `title`, `url`, `snippet`, and `score` fields.

## Search API

`GET /search?q=<query>&page=<page>` validates that `q` is not empty, delegates
ranking to `ranker.rank`, retrieves the selected pages, and returns the agreed
JSON contract: `query`, `total`, `page`, `per_page`, `time_ms`, and `results`.
Each result contains `id`, `title`, `url`, `snippet`, and `score`.

The API reuses PostgreSQL connections between requests. A one-time cold request
creates the pool connection; the following benchmark was taken after that
warm-up request. Every technical benchmark query returned HTTP 200 and met the
under-one-second response target.

| Query | Matching pages | Response time (ms) |
| --- | ---: | ---: |
| information retrieval | 1,567 | 681 |
| search engine | 989 | 656 |
| web crawler | 1,581 | 665 |
| database | 656 | 609 |
| postgresql | 455 | 569 |
| python | 566 | 648 |
| scrapy | 53 | 680 |
| flask | 67 | 576 |
| inverted index | 694 | 553 |
| tf idf | 77 | 553 |
| machine learning | 969 | 596 |
| computer science | 1,034 | 597 |
| data structures | 1,539 | 604 |
| web development | 2,408 | 694 |
| network | 496 | 630 |
| programming | 737 | 593 |
| algorithm | 420 | 581 |
| software engineering | 685 | 556 |
| query | 604 | 552 |
| ranking | 279 | 582 |

The team-owned `docs/test-queries.md` file is still absent, so these figures
measure API performance only; they are not the team's relevance-evaluation set.
