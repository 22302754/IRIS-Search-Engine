# Web Crawler — Report Section (draft)

Author: Mohammed Nouri (Crawler & Infrastructure) · For the final report, chapter "System Design and Implementation"

> Numbers from the crawl of 17 October 2026 (`docs/crawl-report.md`).

## Purpose of the Crawler

The crawler is the first stage of the IRIS pipeline. It collects the documents that the system will later index and rank. It starts from a list of seed URLs, downloads each page, extracts the useful text, and follows the links it finds to discover new pages (Olston & Najork, 2010). Its output is a clean collection of pages stored in the `pages` table of the PostgreSQL database, which the indexer reads in the next stage.

## Design

The crawler is written in Python with the Scrapy framework. It is made of five parts, each in its own file:

| Part | File | Role |
| --- | --- | --- |
| Spider | `crawler/iris_spider.py` | Downloads pages, follows links, applies the per-site rules and limits |
| Site rules | `crawler/sites.json`, `crawler/seeds.txt` | Seed URLs and, for each site, the allowed paths, page limit and depth limit |
| Text cleaner | `crawler/cleaner.py` | Removes markup and boilerplate and returns the title, main text, description and language |
| Duplicate control | `crawler/dedupe.py` | Blocks the same URL and the same text from being stored twice |
| Storage | `crawler/pipelines.py` | Saves each page to PostgreSQL and to a JSON Lines backup file |

**Seed sites and scope.** Six sites were selected: Books to Scrape and Quotes to Scrape (sandboxes built for crawler practice), the Python 3 documentation, the MDN Web Docs, the online edition of the textbook *Introduction to Information Retrieval* (Manning et al., 2008) and the English Wikipedia article on information retrieval and its neighbours. Together they cover programming, web technology and information retrieval, which gives the test queries a realistic and varied collection. For each site, `sites.json` defines regular expressions for the paths that may be followed, so the crawler stays inside the useful area of the site and skips login pages, search results, file downloads and old documentation versions.

**Traversal.** The crawler visits pages breadth-first, so pages close to the seed, which are usually the most important, are collected first. Each site has a page limit and a depth limit. When a site reaches its limit, its remaining queued requests are dropped before download by a small downloader middleware, which saves time and bandwidth.

**Text extraction.** Raw HTML contains much more than the article: menus, headers, footers, sidebars, cookie banners, scripts and styles. Indexing that text would make every page match words such as "home" or "sign in". The cleaner therefore removes these elements by tag (`nav`, `header`, `footer`, `script` …), by ARIA role and by common class and id names, then keeps the main content area (`main`, `article` or the site's content container). Paragraph breaks are preserved so words from different blocks do not join together. Pages with fewer than 30 words are rejected as thin pages.

**Duplicate control.** URLs are first put in a canonical form: the host is lower-cased, the `#fragment` and tracking parameters such as `utm_source` are removed, and query parameters are sorted. A URL is stored only once. Because the same text can also appear at different URLs, each page receives a SHA-1 fingerprint of its normalised text, and a page whose fingerprint has already been seen is skipped. Fingerprints and URLs of earlier runs are loaded from the database at start-up, so a new run only adds new pages.

**Storage.** Each page is written to the `pages` table (`url`, `site`, `title`, `description`, `language`, `text`, `word_count`, `content_hash`, `crawled_at`). Every page is also appended to a JSON Lines file. This file is a backup and lets teammates load the same collection into their own database with `python -m crawler.load_jsonl`, without crawling the sites again.

## Ethical and Legal Considerations

The crawler follows the Robots Exclusion Protocol (Koster et al., 2022): Scrapy downloads each site's `robots.txt` before any page and never requests a disallowed path. Before the crawl, every seed site was checked with `crawler/check_robots.py`. One proposed site, W3Schools, refused to serve its `robots.txt` to automated agents (HTTP 403) and was removed from the seed list. A second site, Real Python, allowed crawling in its `robots.txt` but answered the crawler's requests with HTTP 403; this was treated as a refusal and the site was replaced. The crawler identifies itself with a clear user-agent that names the project and links to its repository. It sends at most one request per second to each site, so it never places a noticeable load on a server. Only the text needed for indexing is kept; images, files and personal data are not collected, and the content is not republished.

## Results

The final crawl, run on 17 October 2026, collected **1,360 pages** containing **2,385,015 words** from six sites in **7 minutes 56 seconds**, using 1,573 HTTP requests (Table X). Every site reached its page limit. A further 75 pages were rejected as too thin, 50 as copies of text already saved and 3 as repeated URLs. Of the 1,573 requests, 1,511 (96%) returned a page directly and most of the rest were redirects. Only six returned HTTP 404: two were the missing `robots.txt` files of the two sandbox sites, which RFC 9309 treats as permission to crawl, and four were Wikipedia links to pages that no longer exist. No page was blocked by `robots.txt`, because the site rules already keep the crawler out of disallowed areas.

*Table X. Pages collected per site.*

| Site | Pages | Avg. words / page | Total words |
| --- | ---: | ---: | ---: |
| Books to Scrape | 250 | 326 | 81,703 |
| Quotes to Scrape | 150 | 156 | 23,475 |
| Python 3 documentation | 250 | 4,194 | 1,048,713 |
| MDN Web Docs | 250 | 948 | 237,045 |
| Introduction to Information Retrieval (online book) | 260 | 637 | 165,776 |
| Wikipedia | 200 | 4,141 | 828,303 |
| **Total** | **1,360** | **1,753** | **2,385,015** |

The collection is deliberately varied. The Python documentation and Wikipedia pages are long reference articles, while Books to Scrape and Quotes to Scrape give many short pages. This mix is useful for testing the ranker, because TF-IDF must work for both long and short documents. One Python documentation page (the full changelog) was skipped because it was larger than the 5 MB download limit.

## Testing

The text cleaner and the duplicate control are covered by unit tests in `tests/test_cleaner.py` and `tests/test_dedupe.py` (16 tests, run with `pytest`). They check that boilerplate is removed, paragraphs stay separated, thin pages are rejected, URL variants are treated as the same page, and that the per-site rules accept and reject the right URLs. The full crawler was also tested end to end against six local test sites that contain menus, cookie banners, duplicate pages, thin pages and paths blocked by `robots.txt`: no boilerplate text, duplicate URL, duplicate text or blocked page reached the database.

## References

Manning, C. D., Raghavan, P., & Schütze, H. (2008). *Introduction to information retrieval*. Cambridge University Press.


Koster, M., Illyes, G., Zeller, H., & Sassman, L. (2022). *Robots Exclusion Protocol* (RFC 9309). Internet Engineering Task Force. https://www.rfc-editor.org/rfc/rfc9309

Olston, C., & Najork, M. (2010). Web crawling. *Foundations and Trends in Information Retrieval, 4*(3), 175–246.
