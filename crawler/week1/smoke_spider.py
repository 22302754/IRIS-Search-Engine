"""
IRIS - Week 1 test spider.

Crawls ONE seed site, stops after 20 pages, and prints the title and URL
of every page. It obeys robots.txt and waits between requests.

Run (from the repository root):
    scrapy runspider crawler/week1/smoke_spider.py -a start_url=https://books.toscrape.com/ -O crawler/week1/sample_pages.json
"""
from datetime import datetime, timezone
from urllib.parse import urlparse

import scrapy


class TestSpider(scrapy.Spider):
    name = "iris_test"

    custom_settings = {
        "ROBOTSTXT_OBEY": True,            # respect robots.txt (RFC 9309)
        "DOWNLOAD_DELAY": 1.0,             # 1 second between requests
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CLOSESPIDER_PAGECOUNT": 20,       # stop after 20 pages
        "DEPTH_LIMIT": 3,
        "USER_AGENT": "IRIS-StudentCrawler/0.1 (CIU capstone project; +https://github.com/22302754/iris-search-engine)",
        "LOG_LEVEL": "INFO",
        "FEED_EXPORT_ENCODING": "utf-8",
    }

    def __init__(self, start_url="https://books.toscrape.com/", max_pages=20, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = [start_url]
        self.allowed_domains = [urlparse(start_url).hostname]
        self.max_pages = int(max_pages)
        self.count = 0

    def parse(self, response):
        if self.count >= self.max_pages:
            return
        self.count += 1

        title = (response.css("title::text").get() or "").strip()
        print(f"[{self.count:02d}] {title} -> {response.url}")

        yield {
            "url": response.url,
            "title": title,
            "crawled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

        # follow links on the same site only
        for href in response.css("a::attr(href)").getall():
            if href.startswith(("mailto:", "javascript:", "#")):
                continue
            yield response.follow(href, callback=self.parse)
