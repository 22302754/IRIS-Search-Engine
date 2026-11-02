# Seed Sites – robots.txt Check

Checked: 9 October 2026 · updated 20 October and 2 November 2026 · Owner: Mohammed (Crawler & Infrastructure)

Run `python crawler/check_robots.py` to re-check at any time.

| Seed URL | robots.txt result | Pages we must avoid | Decision |
| --- | --- | --- | --- |
| https://books.toscrape.com/ | No robots.txt (404) → everything allowed | – | Keep (built for crawler practice) |
| https://quotes.toscrape.com/ | No robots.txt (404) → everything allowed | – | Keep (built for crawler practice) |
| https://docs.python.org/3/ | Allowed | `/dev`, `/release`, old versions (`/2/`, `/3.0/`–`/3.10/`) | Keep |
| https://developer.mozilla.org/en-US/docs/Web | Allowed | `/api/`, `/*/files/`, `/media` | Keep |
| https://nlp.stanford.edu/IR-book/html/htmledition/irbook.html | Allowed (until 1 Nov) | `/manual`, `/viewvc` | **Paused 2 Nov**: the server refuses all connections. The 253 saved pages stay searchable (the book does not change) |
| https://en.wikipedia.org/wiki/Information_retrieval | Allowed | admin and special pages (handled by Scrapy) | Keep; use a low page limit |
| https://www.postgresql.org/docs/current/ | Allowed | `/docs/devel/`, `/admin/`, `/account/`, `/list/`, `/search/`, `/message-id/...` | Added week 3 (our database; includes the full-text search chapter) |
| https://docs.scrapy.org/en/latest/ | Allowed | `/en/stable/` and old versions are hidden by Read the Docs, so we use `/en/latest/` | Added week 3 (our crawler framework) |
| https://flask.palletsprojects.com/en/stable/ | Allowed | `/en/latest/` is hidden by Read the Docs, so we use `/en/stable/` | Added week 3 (our web framework) |
| https://ciu.edu.tr/en | Checked by `check_robots.py` before the first crawl | Only the public English pages (`/en/...`); never SIS, Moodle, webmail or the application portal (other hosts, which the crawler never leaves its host for) | Added week 5 (our university: programmes, academic calendar, fees, student life, news) |

Removed

- https://www.w3schools.com/python/ – the server refuses robots.txt to our crawler (HTTP 403), so it does not want automated access. Dropped from the seed list.
- https://realpython.com/ – robots.txt allows crawling, but the server answers our crawler's page requests with HTTP 403 (bot protection), so we respect that and do not crawl it. Replaced by the online edition of *Introduction to Information Retrieval* (Manning, Raghavan & Schütze), which also fits the project topic.

Notes

- Our crawler uses `ROBOTSTXT_OBEY = True`, so Scrapy skips all disallowed paths automatically.
- CIU: only public pages on `ciu.edu.tr/en` are crawled. Pages behind a login (SIS, Moodle, webmail, the
  application portal) are on other hosts and hold personal data, so they are never crawled.
- None of the checked sites sets a crawl-delay; we still wait 1 second between requests to be polite.
- Under RFC 9309, a missing robots.txt (404) means crawling is allowed.
