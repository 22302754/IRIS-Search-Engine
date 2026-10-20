# IRIS Crawler

Owner: Mohammed (Computer Engineering). All commands run from the **repository root**.

## Files

| File | What it does |
| --- | --- |
| `seeds.txt` | Start URLs, one per line |
| `sites.json` | Rules per site: allowed paths, page limit, depth limit |
| `iris_spider.py` | The crawler (Scrapy spider) |
| `cleaner.py` | Turns HTML into clean text: title, main text, description, language |
| `dedupe.py` | Blocks the same URL and the same text from being saved twice |
| `pipelines.py` | Saves new pages and updates changed pages in PostgreSQL and `output/pages.jsonl` |
| `pages_table.sql` | The `pages` table the crawler fills (copy into `docs/schema.sql`) |
| `run_crawl.py` | Starts the crawl |
| `crawl_report.py` | Writes `docs/crawl-report.md` from the crawl output |
| `load_jsonl.py` | Loads `pages.jsonl` into any database (local or cloud): adds new, updates changed |
| `check_robots.py` | Checks every seed against its robots.txt |
| `week1/` | Week 1 smoke spiders, robots check and sample output (kept for reference) |

## Run

```bash
pip install scrapy psycopg2-binary pytest

python3 run_pipeline.py                              # robots check -> crawl -> report -> index (repository root)
python3 -m crawler.run_crawl                         # crawl only
python3 -m crawler.crawl_report                      # writes docs/crawl-report.md
python3 -m pytest                                    # unit tests

# quick test that touches neither your database nor your real output file
python3 -m crawler.run_crawl --max-pages 5 --no-db --out /tmp/test.jsonl --fresh
```

Other options: `--only books,mdn` (some sites only), `--delay 2` (slower), `--log-level WARNING` (quieter).

## Incremental re-crawl

Every run starts from the pages already saved (in the database and in `output/pages.jsonl`):

| Page | What happens |
| --- | --- |
| Never seen before | saved as **new** (only while the site is below its `max_pages`) |
| Seen before, text changed | saved again as an **update**, `updated_at` = now |
| Seen before, text the same | counted as **unchanged**, nothing written |

`max_pages` is the target size of the collection for each site. Running again with the same limits only
checks the old pages; raising a limit adds exactly the difference as new pages. Pages at the depth limit
that were seen before are requested with `If-None-Match` / `If-Modified-Since`, so an unchanged page
answers `304 Not Modified` without sending its content again.

`--fresh` only starts a new `pages.jsonl`; the database keeps its pages.

## Database

Put the connection in a `.env` file in the repository root (never commit it):

```
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/iris
```

With `DATABASE_URL` set, pages are also saved to the `pages` table. The table is created if it
does not exist. If the team's table has fewer columns, only the existing columns are filled.

Teammates load the shared crawl into their own database with:

```bash
python -m crawler.load_jsonl path/to/pages.jsonl
```

## Output

`crawler/output/` is not committed to Git (it is large and can be regenerated).
Share `pages.jsonl` with the team through the group chat or a shared drive.
