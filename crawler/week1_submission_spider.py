"""Personal Week 1 crawler smoke-test submission.

This file is intentionally standalone. It does not replace the team's crawler
files or alter the production crawl configuration.
"""

from __future__ import annotations

from urllib.parse import urlparse

import scrapy
from scrapy.linkextractors import LinkExtractor


class Week1SubmissionSpider(scrapy.Spider):
    """Visit at most 20 approved in-domain pages and log title and URL."""

    name = "week1_submission_smoke"
    DEFAULT_PAGE_LIMIT = 20

    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 1.0,
        "DOWNLOAD_DELAY_JITTER": 0,
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DEPTH_LIMIT": 2,
        "USER_AGENT": "IRIS-StudentCrawler/0.1 (CIU capstone project)",
        "LOG_LEVEL": "INFO",
    }

    def __init__(
        self,
        start_url: str = "https://books.toscrape.com/",
        page_limit: int | str = DEFAULT_PAGE_LIMIT,
        *args: object,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)

        parsed = urlparse(start_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("start_url must be an absolute http(s) URL")

        self.page_limit = int(page_limit)
        if self.page_limit < 1:
            raise ValueError("page_limit must be at least 1")

        self.start_urls = [start_url]
        self.allowed_domains = [parsed.hostname.lower()]
        self._links = LinkExtractor(allow_domains=self.allowed_domains)
        self._processed_pages = 0
        # The seed request counts toward the cap. This prevents a large queue of
        # requests from being created before the limit is reached.
        self._scheduled_pages = 1

    def parse(self, response: scrapy.http.Response):
        if self._processed_pages >= self.page_limit:
            return

        self._processed_pages += 1
        title = " ".join(response.css("title::text").getall()).strip()
        self.logger.info(
            "PAGE %02d title=%r url=%s",
            self._processed_pages,
            title or "(untitled)",
            response.url,
        )

        yield {"title": title, "url": response.url}

        for link in self._links.extract_links(response):
            if self._scheduled_pages >= self.page_limit:
                break
            self._scheduled_pages += 1
            yield response.follow(link.url, callback=self.parse)
