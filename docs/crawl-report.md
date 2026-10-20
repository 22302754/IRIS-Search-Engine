# Crawl Report

Generated: 20 October 2026, 20:57 · Owner: Mohammed (Crawler)

The collection holds **3,769 pages** and **6,459,362 words** from **9 sites**.
The last crawl covered only: scrapy-docs ("–" = site not in the last crawl).
The last crawl took **1 min 42 s**, sent 56 requests and finished with reason `finished`.

## Pages per site

| Site | Seed URL | Pages | Avg. words / page | Total words | Target size | New (last run) | Updated (last run) | Unchanged (last run) | Download errors (last run) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| books | https://books.toscrape.com/ | 938 | 338 | 317,825 | 1000 | – | – | – | – |
| quotes | https://quotes.toscrape.com/ | 176 | 151 | 26,740 | 250 | – | – | – | – |
| python-docs | https://docs.python.org/3/ | 520 | 2,937 | 1,527,566 | 700 | – | – | – | – |
| mdn | https://developer.mozilla.org/en-US/docs/Web | 700 | 638 | 447,247 | 700 | – | – | – | – |
| ir-book | https://nlp.stanford.edu/IR-book/html/htmledition/irbook.html | 260 | 582 | 151,577 | 260 | – | – | – | – |
| wikipedia | https://en.wikipedia.org/wiki/Information_retrieval | 600 | 5,347 | 3,208,214 | 600 | – | – | – | – |
| postgresql-docs | https://www.postgresql.org/docs/current/ | 450 | 1,217 | 547,682 | 450 | – | – | – | – |
| scrapy-docs | https://docs.scrapy.org/en/latest/ | 53 | 2,620 | 138,879 | 200 | 53 | 0 | 0 | 0 |
| flask-docs | https://flask.palletsprojects.com/en/stable/ | 72 | 1,300 | 93,632 | 150 | – | – | – | – |
| **Total** | | **3,769** | **1,713** | **6,459,362** | **4,310** | **53** | **0** | **0** | **0** |

## Pages not saved (last run)

| Reason | Pages |
| --- | ---: |
| Same text as a page already saved | 1 |
| Too little text (menus, redirects, empty pages) | 1 |
| Blocked by robots.txt | 0 |

## HTTP status codes (last run)

| Status | Responses |
| --- | ---: |
| 200 | 56 |

## Page language

| Language | Pages |
| --- | ---: |
| en | 3,762 |
| unknown | 7 |

## How to reproduce

```bash
python -m crawler.run_crawl --fresh
python -m crawler.crawl_report
```
