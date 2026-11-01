# Testing — Report Section

Owner: Software Engineer #2 (Interface, Testing & Scrum) · Tests: `tests/` · Automation: `.github/workflows/tests.yml`

## Strategy

IRIS is tested at four levels, from single functions to the running system:

| Level | What is checked | How |
| --- | --- | --- |
| Unit | One function with known input and output: text cleaning, duplicate detection, `preprocess()`, TF-IDF weights, snippets | `pytest`, no network, no database |
| Integration | Modules working together: crawler + database, `rank()` on real SQL, the Flask routes with the search backend | `pytest` with a throw-away PostgreSQL database, local test web sites and Flask's test client |
| System | The deployed engine answers the 20 test queries in under one second (NFR-1) | `python3 -m infra.smoke_test` against the live URL |
| Data | The crawled collection itself: unknown language, very short or long pages, menu text, duplicate titles, near-duplicates | `python3 -m infra.check_quality` |

Every test is automated and repeatable. Tests that need the network or the team database are kept out of the unit
suite, so the whole suite runs in a few seconds on any laptop.

## Automated Test Suite

The suite contains **104 tests** in ten files:

| File | Tests | Module | Main cases |
| --- | ---: | --- | --- |
| `test_cleaner.py` | 13 | Crawler | menus, headers, footers and scripts removed; main text kept; URL canonical form; thin pages rejected |
| `test_dedupe.py` | 6 | Crawler | same URL or same text saved only once |
| `test_incremental.py` | 13 | Crawler | new / changed / unchanged pages on a re-crawl, `304 Not Modified`, stale pages removed |
| `test_week1_submission.py` | 3 | Crawler | the week 1 robots.txt check and test spider |
| `test_quality.py` | 6 | Infrastructure | data-quality checks, SimHash near-duplicates |
| `test_preprocess.py` | 9 | Pre-processing | empty text, mixed case, punctuation, numbers, stop words, stemming, URLs, short words |
| `test_search_modules.py` | 7 | Indexer | term and document frequencies, vector norms, empty collection |
| `test_rank.py` | 29 | Ranker | hand-calculated TF-IDF and cosine scores for 3 documents and 2 queries, result order, unknown words, empty and stop-word-only queries — run in Python and again on PostgreSQL |
| `test_web.py` | 12 | Web / API | `/search` JSON fields, HTTP 400 for an empty query, no results, backend down (HTTP 503), paging (10 per page) |
| `test_snippet.py` | 6 | Web | snippet around the first query word, word forms through stemming, bold query words, HTML escaping |

The ranking tests are the most important: they compare the scores of `rank()` with values calculated by hand,
so an error in the formula, in the use of `page_norms` or in the SQL is found at once. The same cases run twice —
once against a small in-memory index and once against a real PostgreSQL server — so the Python and SQL versions of
the formula are known to agree.

The web tests replace the database with a fixed list of results (`SEARCH_PROVIDER`), so the page, the paging and
the error states are tested without a network. The snippet tests include a page containing `<script>`, which must
appear escaped, to make sure that page text can never run as code in a visitor's browser.

## Continuous Integration

`.github/workflows/tests.yml` runs the whole suite on GitHub Actions for every pull request and every push to
`main`. A PostgreSQL 16 container is started next to the tests, so the ranking tests also run on a real database
server; it is a fresh, empty database, never the team's data. Because `main` is protected and needs a reviewed pull
request, a change whose tests fail is visible before it is merged.

## System and Data Tests

**Response time (NFR-1).** The smoke test sends the 20 evaluation queries in `docs/test-queries.json` to the
running engine and records the HTTP status, the number of results and the response time of each. After the
database connections were made reusable, all 20 benchmark queries were answered in 552–694 ms
([indexing section](indexing-section.md)). The figures for the deployed site are added after deployment:
**[…] of 20** queries under one second, median **[…] ms**.

**Data quality.** On 1 November 2026 the data-quality check of the 3,769 pages found 7 pages with unknown language,
91 very short pages (< 50 words), 25 very long pages (> 20,000 words), 7 repeated template lines, 32 groups of
duplicate titles and 59 near-duplicate pairs. These are reviewed by the crawler owner; the 7 unknown-language pages
are removed by the next crawl of the IR textbook.

**Test queries.** `python3 -m ranker.check_queries` confirms that each of the 20 queries has at least one relevant
page in the collection before relevance is judged. The first run found three queries without one (Q12–Q14); they
were corrected or replaced before any judging, as recorded in `docs/test-queries.md`.

## Manual Tests

| Test | Result |
| --- | --- |
| Search page in Chrome, Safari and Firefox on a laptop screen (NFR-8) | **[…]** |
| Keyboard only: type a query, press Enter, move through results with Tab | **[…]** |
| Very long query (500 characters) and special characters (`<`, `"`, `%`) | **[…]** |

## Limitations

The unit tests use small, hand-made examples, so they prove that the formulas are implemented correctly, not that
the ranking is good. The quality of the ranking is measured separately with Precision@10 over the 20 judged
queries (see the evaluation section).
