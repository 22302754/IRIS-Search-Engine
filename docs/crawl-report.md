# Crawl Report

Generated: 02 November 2026, 21:39 · Owner: Mohammed (Crawler)

Pages counted from the database.

The collection holds **4,697 pages** and **7,657,708 words** from **10 sites**.
The last crawl covered only: ciu ("–" = site not in the last crawl).
The last crawl took **21 min 44 s**, sent 954 requests and finished with reason `finished`.

## Pages per site

| Site | Seed URL | Pages | Avg. words / page | Total words | Target size | New (last run) | Updated (last run) | Unchanged (last run) | Download errors (last run) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| books | https://books.toscrape.com/ | 938 | 338 | 317,825 | 1000 | – | – | – | – |
| quotes | https://quotes.toscrape.com/ | 176 | 151 | 26,740 | 250 | – | – | – | – |
| python-docs | https://docs.python.org/3/ | 521 | 2,938 | 1,530,833 | 700 | – | – | – | – |
| mdn | https://developer.mozilla.org/en-US/docs/Web | 700 | 641 | 448,715 | 700 | – | – | – | – |
| wikipedia | https://en.wikipedia.org/wiki/Information_retrieval | 600 | 5,346 | 3,207,861 | 600 | – | – | – | – |
| postgresql-docs | https://www.postgresql.org/docs/current/ | 450 | 1,217 | 547,682 | 450 | – | – | – | – |
| scrapy-docs | https://docs.scrapy.org/en/latest/ | 53 | 2,620 | 138,879 | 200 | – | – | – | – |
| flask-docs | https://flask.palletsprojects.com/en/stable/ | 72 | 1,300 | 93,632 | 150 | – | – | – | – |
| ciu | https://ciu.edu.tr/en | 934 | 1,278 | 1,194,388 | 900 | 315 | 0 | 475 | 2 |
| ir-book |  | 253 | 597 | 151,153 |  | – | – | – | – |
| **Total** | | **4,697** | **1,630** | **7,657,708** | **4,950** | **315** | **0** | **475** | **2** |

## Pages not saved (last run)

| Reason | Pages |
| --- | ---: |
| Too little text (menus, redirects, empty pages) | 83 |
| Same text as a page already saved | 5 |
| Redirected outside the allowed area | 3 |
| Blocked by robots.txt | 2 |

## HTTP status codes (last run)

| Status | Responses |
| --- | ---: |
| 200 | 898 |
| 301 | 54 |
| 404 | 2 |

## Page language

| Language | Pages |
| --- | ---: |
| en | 4,697 |

## How to reproduce

```bash
python -m crawler.run_crawl --fresh
python -m crawler.crawl_report
```
