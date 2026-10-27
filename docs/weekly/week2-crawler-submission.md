# Week 2 — Crawler Run Report

**Owner:** Computer Engineer / Crawler  
**Run date:** 18 October 2026  
**Run command:** `python -m crawler.run_crawl --fresh`

## Scope and implementation

The crawler reads the six configured seeds from `crawler/seeds.txt` and applies the per-site limits and allowed-path/depth rules in `crawler/sites.json`. It uses `crawler/iris_spider.py` to:

- respect `robots.txt`, use the project user agent, and wait at least one second between requests to the same domain;
- extract cleaned page text while retaining the title, language, and meta description;
- remove boilerplate such as scripts, styles, navigation, headers, and footers;
- canonicalize URLs and reject duplicate URLs and duplicate text hashes; and
- persist cleaned records through the database pipeline when `DATABASE_URL` is configured, with JSONL fallback otherwise.

No database connection was configured for this local run, so `crawler/output/pages.jsonl` was used as the intended fallback. Generated crawl data is ignored by Git and was not added to the repository.

## Ethics and preflight

Before the crawl, `crawler/check_robots.py` was run using `IRIS-StudentCrawler/0.1`. All six seeds were allowed. The crawl used `ROBOTSTXT_OBEY=True`, a one-request-per-domain concurrency limit, and the configured page/depth caps. It did not submit forms, authenticate, or access pages outside the configured paths.

## Results

The crawl finished normally after **398.1 seconds** and wrote **1,360 clean pages**, exceeding the Week 2 minimum of 1,000 pages.

| Site | Page cap | Depth cap | Pages saved | Words | Download errors |
|---|---:|---:|---:|---:|---:|
| books | 250 | 4 | 250 | 81,703 | 0 |
| quotes | 150 | 4 | 150 | 23,475 | 0 |
| python-docs | 250 | 4 | 250 | 1,048,750 | 0 |
| mdn | 250 | 3 | 250 | 236,679 | 0 |
| ir-book | 260 | 3 | 260 | 166,137 | 0 |
| wikipedia | 200 | 2 | 200 | 828,179 | 4 |
| **Total** | **1,360** | — | **1,360** | **2,384,923** | **4** |

The downloader made 1,572 requests and received 1,572 responses: 1,511 returned HTTP 200, six returned 404, 51 redirected with 308, and four redirected with 302. The cleaner/deduplicator skipped 75 thin pages, three duplicate URLs, and 50 duplicate-text pages. One oversized Python documentation response was safely rejected by the configured 5 MB download-size limit.

The four counted download failures occurred while crawling Wikipedia, but its configured target of 200 clean pages was still reached. No page was blocked by `robots.txt`.

## Verification

```text
python -m pytest -q
16 passed, 1 warning
```

The warning is a pytest collection warning for the existing `TestSpider` Scrapy class, which has an `__init__` method; it does not indicate a test failure.
