# Week 4 - Infrastructure Index Run

Owner: Crawler & Infrastructure

## Completed on 1 November 2026

- Installed the checked-in project dependencies and ran the complete suite: **49 passed**.
- Verified the shared Supabase PostgreSQL database contains **3,769 pages**.
- Updated the indexer to read page text in keyset-paginated batches of 100 rows. This avoids a large result set being disconnected by the Supabase pooler before the index transaction begins.
- Rebuilt the complete TF-IDF index successfully in one transaction:
  - Pages indexed: **3,769**
  - Terms: **85,640**
  - Postings: **1,201,490**
  - Build time: **921.4 seconds** (15 min 21 sec)
- Verified the live JSON search endpoint with `information retrieval`: HTTP 200, 1,567 matching documents, 10 returned results, and all required result fields.

## Security

The Supabase `DATABASE_URL` was supplied through the local environment for this run only. It is not stored in this document, Git, or any committed configuration file.

## Remaining access task

Branch protection for `main` still needs a repository administrator. The current account can access the repository but does not have Repository Options permission.
