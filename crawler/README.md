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
| `pipelines.py` | Saves pages to PostgreSQL and to `output/pages.jsonl` |
| `pages_table.sql` | The `pages` table the crawler fills (copy into `docs/schema.sql`) |
| `run_crawl.py` | Starts the crawl |
| `crawl_report.py` | Writes `docs/crawl-report.md` from the crawl output |
| `load_jsonl.py` | Loads `pages.jsonl` into a teammate's own database |
| `check_robots.py` | Checks every seed against its robots.txt |
| `test_spider.py` | Week 1 test spider (kept for reference) |

## Run

```bash
pip install scrapy psycopg2-binary pytest

python -m crawler.run_crawl --max-pages 5 --fresh   # quick test: 5 pages per site
python -m crawler.run_crawl --fresh                 # full crawl (about 1,300 pages, 10-25 min)
python -m crawler.crawl_report                      # writes docs/crawl-report.md
python -m pytest tests                              # unit tests
```

Other options: `--only books,mdn` (some sites only), `--delay 2` (slower), `--log-level WARNING` (quieter).
Running again **without** `--fresh` keeps the old pages and only adds new ones.

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
