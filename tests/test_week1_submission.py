from urllib.error import HTTPError

import pytest
from scrapy.http import HtmlResponse, Request

from crawler.week1 import week1_robots_check
from crawler.week1.week1_submission_spider import Week1SubmissionSpider


def make_response(url: str, body: str) -> HtmlResponse:
    return HtmlResponse(
        url=url,
        body=body.encode("utf-8"),
        encoding="utf-8",
        request=Request(url),
    )


def test_smoke_spider_schedules_no_more_than_page_limit() -> None:
    spider = Week1SubmissionSpider(start_url="https://example.test/", page_limit=2)
    response = make_response(
        "https://example.test/",
        """
        <html><head><title>Seed page</title></head><body>
          <a href="/first">First</a>
          <a href="/second">Second</a>
          <a href="https://outside.test/ignored">Outside</a>
        </body></html>
        """,
    )

    results = list(spider.parse(response))

    assert results[0] == {"title": "Seed page", "url": "https://example.test/"}
    assert [request.url for request in results[1:]] == ["https://example.test/first"]
    assert spider._scheduled_pages == 2


def test_robots_url_requires_absolute_http_url() -> None:
    with pytest.raises(ValueError):
        week1_robots_check.robots_url_for("/relative")


def test_missing_robots_file_is_reported_as_allowed(monkeypatch) -> None:
    def missing_robots(*_args, **_kwargs):
        raise HTTPError("https://example.test/robots.txt", 404, "Not Found", None, None)

    monkeypatch.setattr(week1_robots_check, "urlopen", missing_robots)

    robots_url, allowed, detail = week1_robots_check.check_url(
        "https://example.test/path"
    )

    assert robots_url == "https://example.test/robots.txt"
    assert allowed is True
    assert "404" in detail
