# Infrastructure and Deployment — Report Section (draft)

Author: Mohammed Nouri (Crawler & Infrastructure) · For the final report, chapter "System Design and Implementation"

> Numbers marked **[…]** are filled in after the first deployment, backup and smoke test.

## Overview

IRIS runs entirely on free cloud services, so the team, the supervisor and the examiners use the same live system
without installing anything. Three pieces work together: a PostgreSQL database on Supabase that stores the pages and
the index, the Flask web application on Render that answers queries, and a scheduled job on GitHub Actions that
keeps the collection up to date. The total running cost is zero, in line with the cost feasibility study, which
expected free tiers to bring the hosting cost close to nothing.

| Component | Service (free plan) | Role |
| --- | --- | --- |
| Database | Supabase PostgreSQL, Frankfurt | `pages`, `terms`, `postings`, `page_norms` |
| Web application | Render web service, Frankfurt | Flask app served by Gunicorn |
| Scheduled crawl | GitHub Actions | Weekly backup, re-crawl, report, index and quality check |
| Source code | GitHub | Pull requests reviewed before merging into `main` |

## Shared Cloud Database

Each member first worked with a local PostgreSQL database, which meant four copies of the data and no common
index. In week 3 the collection was moved to a single Supabase project in Frankfurt, the region closest to Cyprus.
The crawler and the loading tool write to it directly, using batched inserts of 500 rows so that loading the 3,769
pages takes about two minutes over the internet. Every program reads the connection string from an environment
variable (`DATABASE_URL`), so switching between a local and the cloud database needs no code change. The
password is shared privately and is never stored in Git. Row-level security is enabled on all five tables (`pages`, `terms`, `postings`, `page_norms` and the indexer's
checkpoint table `index_state`), which
closes Supabase's automatic public web API while the application, connecting as the database owner, keeps full
access.

## Web Application Hosting

The Flask application is deployed on Render from a `render.yaml` blueprint kept in the repository. Render builds the
application from `requirements.txt` and starts it with Gunicorn using two worker processes; every merge into `main`
is deployed automatically, so the live site always matches the reviewed code. The database connection string is
entered as a secret in the Render dashboard. The free plan stops the service after 15 minutes without traffic and
the next request takes about a minute to start it again, which is acceptable for a student project as long as the
site is opened shortly before a demonstration. Public URL: **[…]**.

## Scheduled Re-crawl

A GitHub Actions workflow runs every Monday at 02:00 UTC and can also be started by hand. It backs up the database,
runs the full pipeline (robots.txt check, incremental crawl, crawl report, and the indexer, which re-indexes only
the pages changed since its last checkpoint) and runs the data-quality check,
then attaches the reports and the backup to the run for 30 days. Because the crawl is incremental, a weekly run
mostly confirms unchanged pages — many with a short `304 Not Modified` answer — and only writes the pages that are
new or changed. Old pages are also removed when they now return HTTP 404 or 410, when their text has become a
copy of another page, or when they have become too short to index (for example an IR textbook page that holds only
navigation once the menu text is cleaned away), so the collection never keeps stale versions. In a test against
local sites, two pages turned into stubs and one deleted page were removed from both the database and the backup
file in the next run. The weekly activity also prevents the free Supabase project from pausing after seven idle days.

## Backups

Before any automated change the database is backed up with a small Python tool that exports each table to a
gzipped CSV file using PostgreSQL's `COPY` command, together with the table definitions and a manifest of row
counts. This avoids depending on the `pg_dump` program, whose version must match the server. The restore tool
recreates the tables, loads the files, resets the ID sequences and compares the row counts with the manifest before
committing; it refuses to overwrite non-empty tables or the source database unless explicitly forced. A test
restore into a local database reproduced every table exactly. The cloud backup takes **[…] seconds** and **[…] MB**.

## Search Speed

The requirement is an answer in under one second (NFR-1). The first measurement of the live `/search` endpoint,
for the query *information retrieval* (1,567 matching pages), took 3,183 ms. The database part was examined with
PostgreSQL's `EXPLAIN ANALYZE`: the ranking query reads the 2,326 postings of the two query terms through the
`postings(term_id)` index and joins them with `page_norms`, and it runs in about 7.5 ms once the data is in the
server's memory (about 2.3 s for the very first query after the free database has been idle). The time was
therefore spent outside the query. Two causes were found and fixed in the web application: every search opened a
new encrypted connection to the cloud database, and the NLTK stemmer was loaded during the first search. The
application now keeps a small pool of open connections in each worker process, replaces a connection the server
has closed, and loads the ranking module when the server starts. On a local test database the same search then
took 2–17 ms instead of about 1.2 s. The same check found that `postings` carried two identical indexes on
`page_id`; one was removed, which saves space and makes index builds faster. Response times on the deployed system
are recorded by the smoke test below.

## Data Quality and Performance Checks

A data-quality tool scans the whole collection for problems the crawler might have missed: pages without a known
language, very short or very long pages, lines repeated on at least 30 % of a site's pages (menu or footer text the
cleaner did not remove), duplicate titles, and near-duplicate pages found with 64-bit SimHash fingerprints
(Charikar, 2002). A page with a single changed word lies about 4 bits from the original while unrelated pages lie
about 32 bits apart, so pages within 6 bits are reported. The hashes are split into seven blocks: two hashes that
differ in at most 6 bits must agree on one whole block, so only pages sharing a block are compared, which gave the
same pairs as comparing every page with every other page. On 4,000 test pages the check takes about 13 seconds.
Its first run on the real collection found **[…]**.

A smoke-test tool sends the 20 test queries to the live site and records the response time and result count of
each, measuring the system against the requirement of answering a query in under one second (NFR-1). On the
deployed system, **[…] of 20** queries were answered within one second, with a median of **[…] ms**.

## References

Charikar, M. S. (2002). Similarity estimation techniques from rounding algorithms. In *Proceedings of the 34th
Annual ACM Symposium on Theory of Computing* (pp. 380–388). ACM.
