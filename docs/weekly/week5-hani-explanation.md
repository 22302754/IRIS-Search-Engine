# Week 5 - Hani: Indexer and Search API Talking Points

## Full and incremental indexing

- `python -m indexer.build --full` ignores the checkpoint and rebuilds the
  complete inverted index. It tokenises every crawled page with the shared
  `preprocess()` pipeline, writes `terms`, `postings`, and `page_norms`,
  then records the new checkpoint.
- A normal `python -m indexer.build` is incremental. It reads only pages
  changed after `index_state.last_indexed_at`, replaces those pages' postings,
  removes orphaned rows, refreshes document frequencies and cosine norms, and
  advances the checkpoint only after a successful transaction.
- A full build is required after changing tokenisation because every document's
  terms may have changed. Incremental mode is the usual fast path after a crawl.

## Reliability and speed

- Page reads use keyset-paginated batches and short database connections. TCP
  keep-alives and up to four retries mean a dropped cloud connection retries one
  batch rather than losing a whole build.
- The final index write is one transaction, so a search sees the old complete
  index or the new complete index, never a partial one.
- PostgreSQL `COPY` bulk-loads the postings, then `VACUUM (ANALYZE)` refreshes
  statistics for fast index-only scans.

## `/search` API

- `GET /search?q=<query>&page=<page>[&site=<site>]` rejects an empty query
  with HTTP 400 and returns the query, total, page, timing, and ten result
  objects per page.
- Query preprocessing matches document preprocessing. Results require every
  query term, use TF-IDF cosine similarity, and add the documented title bonus.
- `ranker.search.search_page()` performs scoring and result details in two
  database round trips. The Flask route reuses a small PostgreSQL connection
  pool and retries once if the cloud server has closed an idle connection.

## Week 5 checks

- The public-site smoke test on 24 November 2026 returned HTTP 200 for all 20
  official evaluation queries: median 191 ms, slowest 571 ms, and all were
  below the one-second target.
- The local test suite completed with 100 passed and 22 skipped tests.
