# Web Crawler — Report Section (draft)

Author: Mohammed Nouri (Crawler & Infrastructure) · For the final report, chapter "System Design and Implementation"

> Numbers from the crawls of 18 and 20 October 2026 (`docs/crawl-report.md`, `docs/week2-crawler-submission.md`).

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

**Seed sites and scope.** Six sites were selected: Books to Scrape and Quotes to Scrape (sandboxes built for crawler practice), the Python 3 documentation, the MDN Web Docs, the online edition of the textbook *Introduction to Information Retrieval* (Manning et al., 2008) and the English Wikipedia article on information retrieval and its neighbours. In week 3 three documentation sites were added to grow the collection: the PostgreSQL manual (which includes a chapter on full-text search), the Scrapy documentation and the Flask documentation, the same three tools this project is built with. Together the nine sites cover programming, web technology, databases and information retrieval, which gives the test queries a realistic and varied collection. For each site, `sites.json` defines regular expressions for the paths that may be followed, so the crawler stays inside the useful area of the site and skips login pages, search results, file downloads and old documentation versions.

**Traversal.** The crawler visits pages breadth-first, so pages close to the seed, which are usually the most important, are collected first. Each site has a page limit and a depth limit. When a site reaches its limit, its remaining queued requests are dropped before download by a small downloader middleware, which saves time and bandwidth.

**Text extraction.** Raw HTML contains much more than the article: menus, headers, footers, sidebars, cookie banners, scripts and styles. Indexing that text would make every page match words such as "home" or "sign in". The cleaner therefore removes these elements by tag (`nav`, `header`, `footer`, `script` …), by ARIA role and by common class and id names, then keeps the main content area (`main`, `article` or the site's content container). Paragraph breaks are preserved so words from different blocks do not join together. Comment-marked navigation panels, such as the Next / Up / Previous links that the IR textbook repeats at the top and bottom of every page, and `address` footers are removed as well. When a page does not declare its language, the site's default from `sites.json` is used. Pages with fewer than 30 words are rejected as thin pages.

**Duplicate control.** URLs are first put in a canonical form: the host is lower-cased, the `#fragment` and tracking parameters such as `utm_source` are removed, and query parameters are sorted. A URL is stored only once. Because the same text can also appear at different URLs, each page receives a SHA-1 fingerprint of its normalised text, and a page whose fingerprint has already been seen is skipped. Fingerprints and URLs of earlier runs are loaded from the database at start-up.

**Incremental re-crawl.** Web pages change, and re-crawling everything from scratch would waste time and server capacity. Every run therefore starts from the pages already saved and sorts each downloaded page into one of three groups: a page never seen before is stored as new; a known page whose text fingerprint changed is stored again as an update with a new `updated_at` time; and a known page with the same fingerprint is counted as unchanged and not written. Known pages at the depth limit, whose links are not needed, are requested with the HTTP headers `If-None-Match` and `If-Modified-Since` built from the `ETag` and `Last-Modified` values saved earlier; if the page has not changed, the server answers `304 Not Modified` without sending the page again (Fielding & Reschke, 2014). The page limit in `sites.json` is treated as the target size of each site's collection, with old pages counted from the start, so running the crawler again with the same limits only checks for changes, while raising a limit adds exactly the difference as new pages. The indexer can then re-index only the pages whose `updated_at` is newer than its last run.

**Storage.** Each page is written to the `pages` table (`url`, `site`, `title`, `description`, `language`, `text`, `word_count`, `content_hash`, `etag`, `last_modified`, `crawled_at`, `updated_at`). Every page is also appended to a JSON Lines file. This file is a backup and lets teammates load the same collection into their own database with `python -m crawler.load_jsonl`, without crawling the sites again.

## Ethical and Legal Considerations

The crawler follows the Robots Exclusion Protocol (Koster et al., 2022): Scrapy downloads each site's `robots.txt` before any page and never requests a disallowed path. Before the crawl, every seed site was checked with `crawler/check_robots.py`. One proposed site, W3Schools, refused to serve its `robots.txt` to automated agents (HTTP 403) and was removed from the seed list. A second site, Real Python, allowed crawling in its `robots.txt` but answered the crawler's requests with HTTP 403; this was treated as a refusal and the site was replaced. The crawler identifies itself with a clear user-agent that names the project and links to its repository. It sends at most one request per second to each site, so it never places a noticeable load on a server. Only the text needed for indexing is kept; images, files and personal data are not collected, and the content is not republished.

## Results

**First crawl (week 2).** On 18 October 2026 the crawler collected 1,360 pages (2,384,923 words) from six sites in 6 minutes 38 seconds, using 1,572 HTTP requests. Every site reached its page limit, 75 pages were rejected as too thin and 53 as duplicates, and only six requests returned HTTP 404.

**Growing the collection (week 3).** On 20 October 2026 the page limits were raised and three documentation sites were added. Because the crawl is incremental, the 1,360 existing pages were checked rather than collected again (Table X). The first week 3 run added 2,242 new pages, updated 293 pages and found 1,060 unchanged, in 19 minutes 37 seconds. Of the updates, 253 were IR textbook pages whose navigation panels were now removed by the improved cleaner. A second run with the same limits added only 114 pages that the first run had not reached, updated one changed Wikipedia article and confirmed 3,585 pages as unchanged; 362 of these answered `304 Not Modified`, so their content was not downloaded again. This shows that repeated crawls cost little and never duplicate pages.

The second run also exposed a cleaning problem: the Scrapy documentation, built with the Read the Docs theme, wraps each article in a container whose class name contains "nav", so the boilerplate filter removed the whole article and every page was rejected as too thin. After the cleaner was changed to protect the main content area when a page comes out too short, a crawl of that site alone added its 53 pages.

*Table X. The collection after week 3 (20 October 2026).*

| Site | Pages | Avg. words / page | Total words |
| --- | ---: | ---: | ---: |
| Books to Scrape | 938 | 338 | 317,825 |
| Quotes to Scrape | 176 | 151 | 26,740 |
| Python 3 documentation | 520 | 2,937 | 1,527,566 |
| MDN Web Docs | 700 | 638 | 447,247 |
| Introduction to Information Retrieval (online book) | 260 | 582 | 151,577 |
| Wikipedia | 600 | 5,347 | 3,208,214 |
| PostgreSQL documentation | 450 | 1,217 | 547,682 |
| Scrapy documentation | 53 | 2,620 | 138,879 |
| Flask documentation | 72 | 1,300 | 93,632 |
| **Total** | **3,769** | **1,713** | **6,459,362** |

The final collection holds **3,769 pages and 6,459,362 words**, within the 3,000–5,000-page range set in the requirements. Four sites reached their target size (MDN, the IR textbook, Wikipedia and PostgreSQL); the other five stopped earlier because all of their pages reachable within the depth limits had been collected. No page was blocked by `robots.txt`, and the whole collection was loaded into the team's shared Supabase PostgreSQL database.

## Testing

The text cleaner and the duplicate control are covered by unit tests in `tests/test_cleaner.py` and `tests/test_dedupe.py` (31 tests in total with the incremental tests) (run with `pytest`). They check that boilerplate is removed, paragraphs stay separated, thin pages are rejected, URL variants are treated as the same page, and that the per-site rules accept and reject the right URLs. The full crawler was also tested end to end against six local test sites that contain menus, cookie banners, duplicate pages, thin pages and paths blocked by `robots.txt`: no boilerplate text, duplicate URL, duplicate text or blocked page reached the database. The incremental re-crawl is covered by `tests/test_incremental.py` and was tested against three local sites that send `ETag` headers and can edit pages on demand. A second run with no edits stored no new pages, counted all 95 old pages as unchanged and received `304 Not Modified` for 33 of them; after five pages were edited and one site's limit was raised from 40 to 60, the third run stored exactly 20 new pages and updated the edited pages that were in the collection, with no duplicate rows in the database.

## References

Fielding, R., & Reschke, J. (2014). *Hypertext Transfer Protocol (HTTP/1.1): Conditional requests* (RFC 7232). Internet Engineering Task Force. https://www.rfc-editor.org/rfc/rfc7232


Manning, C. D., Raghavan, P., & Schütze, H. (2008). *Introduction to information retrieval*. Cambridge University Press.


Koster, M., Illyes, G., Zeller, H., & Sassman, L. (2022). *Robots Exclusion Protocol* (RFC 9309). Internet Engineering Task Force. https://www.rfc-editor.org/rfc/rfc9309

Olston, C., & Najork, M. (2010). Web crawling. *Foundations and Trends in Information Retrieval, 4*(3), 175–246.
