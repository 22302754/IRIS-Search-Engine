# Crawl Report

Generated: 17 October 2026, 22:22 · Owner: Mohammed (Crawler)

The collection holds **1,360 pages** and **2,385,015 words** from **6 sites**.
The last crawl took **7 min 56 s**, sent 1,573 requests and finished with reason `finished`.

## Pages per site

| Site | Seed URL | Pages | Avg. words / page | Total words | Page limit (per run) | Download errors (last run) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| books | https://books.toscrape.com/ | 250 | 326 | 81,703 | 250 | 0 |
| quotes | https://quotes.toscrape.com/ | 150 | 156 | 23,475 | 150 | 0 |
| python-docs | https://docs.python.org/3/ | 250 | 4,194 | 1,048,713 | 250 | 0 |
| mdn | https://developer.mozilla.org/en-US/docs/Web | 250 | 948 | 237,045 | 250 | 0 |
| ir-book | https://nlp.stanford.edu/IR-book/html/htmledition/irbook.html | 260 | 637 | 165,776 | 260 | 0 |
| wikipedia | https://en.wikipedia.org/wiki/Information_retrieval | 200 | 4,141 | 828,303 | 200 | 4 |
| **Total** | | **1,360** | **1,753** | **2,385,015** | | **4** |

## Pages not saved (last run)

| Reason | Pages |
| --- | ---: |
| Too little text (menus, redirects, empty pages) | 75 |
| Same text as a page already saved | 50 |
| URL already saved | 3 |
| Blocked by robots.txt | 0 |

## HTTP status codes (last run)

| Status | Responses |
| --- | ---: |
| 200 | 1,511 |
| 302 | 4 |
| 308 | 51 |
| 404 | 6 |

## Page language

| Language | Pages |
| --- | ---: |
| en | 1,100 |
| unknown | 260 |

## How to reproduce

```bash
python -m crawler.run_crawl --fresh
python -m crawler.crawl_report
```
