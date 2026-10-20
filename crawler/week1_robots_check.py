"""Personal Week 1 robots.txt preflight utility.

Run before a smoke crawl to check one proposed seed URL. Scrapy's runtime
``ROBOTSTXT_OBEY`` setting is still the crawler's enforcement mechanism.
"""

from __future__ import annotations

import argparse
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

USER_AGENT = "IRIS-StudentCrawler/0.1 (CIU capstone project)"


def robots_url_for(url: str) -> str:
    """Return the robots.txt location for an absolute HTTP(S) URL."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Expected an absolute http(s) URL, got: {url}")
    return urljoin(f"{parsed.scheme}://{parsed.netloc}", "/robots.txt")


def check_url(url: str, timeout: float = 15.0) -> tuple[str, bool, str]:
    """Report whether a seed URL is allowed for this crawler user agent."""
    robots_url = robots_url_for(url)
    policy = RobotFileParser()
    request = Request(robots_url, headers={"User-Agent": USER_AGENT})

    try:
        with urlopen(request, timeout=timeout) as response:
            lines = response.read().decode("utf-8", errors="replace").splitlines()
    except HTTPError as error:
        if error.code == 404:
            return robots_url, True, "robots.txt is not published (HTTP 404)"
        if error.code in {401, 403}:
            return robots_url, False, f"robots.txt denied access (HTTP {error.code})"
        return robots_url, False, f"robots.txt returned HTTP {error.code}"
    except URLError as error:
        return robots_url, False, f"could not fetch robots.txt: {error.reason}"

    policy.parse(lines)
    return robots_url, policy.can_fetch(USER_AGENT, url), "robots.txt loaded"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check whether candidate seed URLs allow the IRIS crawler."
    )
    parser.add_argument("urls", nargs="+", help="Candidate absolute http(s) URLs")
    args = parser.parse_args()

    exit_code = 0
    for url in args.urls:
        robots_url, allowed, detail = check_url(url)
        status = "ALLOWED" if allowed else "BLOCKED"
        print(f"{status}: {url}\n  policy: {robots_url}\n  detail: {detail}")
        exit_code = exit_code or int(not allowed)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
