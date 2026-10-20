"""
IRIS - start the crawl.

Run from the repository root:
    python -m crawler.run_crawl                     # all sites in seeds.txt, limits from sites.json
    python -m crawler.run_crawl --only books,quotes # some sites only
    python -m crawler.run_crawl --fresh             # start a new pages.jsonl (database is kept)
    python -m crawler.run_crawl --max-pages 5 --no-db --out /tmp/test.jsonl --fresh   # quick test

Pages go to crawler/output/pages.jsonl, and to the PostgreSQL `pages` table when
DATABASE_URL is set (in the shell or in a .env file in the repository root).
Statistics go to crawler/output/crawl_stats.json; then run:  python -m crawler.crawl_report
"""
import argparse
from pathlib import Path

from scrapy.crawler import CrawlerProcess
from scrapy.settings import Settings

from crawler.iris_spider import IrisSpider

HERE = Path(__file__).parent


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run the IRIS crawler.")
    ap.add_argument("--seeds", default=str(HERE / "seeds.txt"), help="file with one start URL per line")
    ap.add_argument("--sites", default=str(HERE / "sites.json"), help="per-site rules")
    ap.add_argument("--only", default="", help="comma-separated site names, e.g. books,mdn")
    ap.add_argument("--max-pages", type=int, default=None, help="override the page limit of every site")
    ap.add_argument("--out", default=str(HERE / "output" / "pages.jsonl"), help="JSON Lines output file")
    ap.add_argument("--stats", default=str(HERE / "output" / "crawl_stats.json"), help="statistics file")
    ap.add_argument("--fresh", action="store_true", help="delete the old JSON Lines file before crawling")
    ap.add_argument("--no-db", action="store_true", help="do not use PostgreSQL even if DATABASE_URL is set")
    ap.add_argument("--delay", type=float, default=None, help="seconds between requests to the same site")
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args(argv)

    if args.fresh and Path(args.out).exists():
        Path(args.out).unlink()
        print(f"Deleted old {args.out}")

    settings = {"IRIS_JSONL_FILE": args.out, "IRIS_STATS_FILE": args.stats, "LOG_LEVEL": args.log_level,
                "IRIS_USE_DB": not args.no_db}
    if args.delay is not None:
        settings["DOWNLOAD_DELAY"] = args.delay

    # "cmdline" priority, so these options win over the spider's own defaults
    scrapy_settings = Settings()
    scrapy_settings.setdict(settings, priority="cmdline")
    process = CrawlerProcess(settings=scrapy_settings)
    process.crawl(IrisSpider, seeds=args.seeds, sites=args.sites,
                  only=args.only or None, max_pages=args.max_pages)
    process.start()


if __name__ == "__main__":
    main()
