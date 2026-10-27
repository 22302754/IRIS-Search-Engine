# Meeting Notes and Decisions

Kept by: Software Engineer #2 (Scrum). Newest entries first. A change to `docs/contracts.md` is only valid
when it is written here.

## Decisions log

| Week | Decision | Why |
| --- | --- | --- |
| 3 | Shared cloud PostgreSQL on Supabase (Frankfurt); the connection string is sent privately, never in Git | Everyone searches the same pages and index |
| 3 | Collection grows to 9 sites (PostgreSQL, Scrapy and Flask documentation added); incremental re-crawl | Requirement of 3,000–5,000 pages; only changed pages are downloaded again |
| 2 | Module contracts fixed in `docs/contracts.md`: `pages`, `terms`, `postings`, `page_norms`, `preprocess()`, `rank()`, `/search` JSON | Each member can work alone and the parts still fit |
| 2 | Ranking model: TF-IDF weights with cosine similarity; pre-processing with stop words and Porter stemming | Standard vector space model for ranked retrieval |
| 1–2 | W3Schools and Real Python removed from the seed sites | Their robots.txt does not allow automated crawling |
| 1 | Crawler in Python with Scrapy, 1 request per second per site, robots.txt obeyed | Polite and legal crawling |
| 1 | Roles: Computer Engineer – crawler and infrastructure; AI Engineer – pre-processing and ranking; Software Engineer #1 – indexer and API; Software Engineer #2 – interface, testing and Scrum | One clear owner per module |
| 1 | All work through GitHub branches and reviewed pull requests | Everyone sees and checks the changes |

## Meetings

Copy this block for every meeting.

```
### <date> – <Monday sync / Wednesday check-in / Saturday integration>

Present:
Done since last meeting:
Blocked:
Decisions:
Next steps (who – what – by when):
```
