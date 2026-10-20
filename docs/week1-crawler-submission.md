# Week 1 Crawler Submission

This submission is kept separate from the team's production crawler files.

## Delivered files

- `crawler/week1/week1_robots_check.py` checks a candidate seed URL's `robots.txt`
  policy before crawling.
- `crawler/week1/week1_submission_spider.py` is a Scrapy smoke spider that logs title
  and URL, respects `robots.txt`, waits one second between requests, restricts
  itself to one domain, and schedules no more than 20 pages.
- `tests/test_week1_submission.py` verifies the bounded crawl behavior and the
  robots preflight behavior without contacting external sites.

## Commands

```powershell
python crawler/week1/week1_robots_check.py https://books.toscrape.com/
scrapy runspider crawler/week1/week1_submission_spider.py -a start_url=https://books.toscrape.com/
pytest tests/test_week1_submission.py
```

`books.toscrape.com` is only a development target. The final project seed sites
remain the team's shared decision.
