# Seed Sites – robots.txt Check

Checked: 9 October 2026 · Owner: Mohammed (Crawler & Infrastructure)

Run `python crawler/check_robots.py` to re-check at any time.

| Seed URL | robots.txt result | Pages we must avoid | Decision |
| --- | --- | --- | --- |
| https://books.toscrape.com/ | No robots.txt (404) → everything allowed | – | Keep (built for crawler practice) |
| https://quotes.toscrape.com/ | No robots.txt (404) → everything allowed | – | Keep (built for crawler practice) |
| https://docs.python.org/3/ | Allowed | `/dev`, `/release`, old versions (`/2/`, `/3.0/`–`/3.10/`) | Keep |
| https://developer.mozilla.org/en-US/docs/Web | Allowed | `/api/`, `/*/files/`, `/media` | Keep |
| https://realpython.com/ | Allowed | `/search`, `?q=` URLs, `/practice/`, `/quizzes/`, account pages | Keep |
| https://www.w3schools.com/python/ | Allowed | `/images`, `/code/`, `.aspx` pages | Keep |
| https://en.wikipedia.org/wiki/Information_retrieval | To confirm with the script | – | Keep only if allowed; use a low page limit |

Notes

- Our crawler uses `ROBOTSTXT_OBEY = True`, so Scrapy skips all disallowed paths automatically.
- None of the checked sites sets a crawl-delay; we still wait 1 second between requests to be polite.
- Under RFC 9309, a missing robots.txt (404) means crawling is allowed.
