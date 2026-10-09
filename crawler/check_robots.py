"""
IRIS - robots.txt checker for the proposed seed sites.

For every URL in crawler/seeds.txt it downloads the site's robots.txt
(using OUR crawler's user-agent, like Scrapy does) and reports whether
our crawler is allowed to fetch that URL. Parsing uses Protego, the same
robots.txt parser Scrapy uses, so the result matches the real crawler.

Run (from the repository root):
    python crawler/check_robots.py
"""
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from protego import Protego  # installed together with Scrapy

USER_AGENT = "IRIS-StudentCrawler/0.1 (CIU capstone project; +https://github.com/22302754/iris-search-engine)"
SEEDS_FILE = Path(__file__).with_name("seeds.txt")


def load_seeds(path):
    seeds = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            seeds.append(line)
    return seeds


def fetch_robots(robots_url):
    """Return (status, text). status is the HTTP code, or None on network error."""
    req = urllib.request.Request(robots_url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception as exc:
        return None, str(exc)


def check(url):
    parts = urlparse(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    status, text = fetch_robots(robots_url)

    if status is None:
        return "ERROR  ", f"could not reach robots.txt ({text})"
    if status == 404 or 400 <= status < 500 and status not in (401, 403):
        # RFC 9309: robots.txt unavailable -> crawling allowed
        return "ALLOWED", f"no robots.txt (HTTP {status})"
    if status in (401, 403):
        return "BLOCKED", f"robots.txt itself is forbidden (HTTP {status})"
    if status >= 500:
        return "BLOCKED", f"server error on robots.txt (HTTP {status}); try again later"

    rp = Protego.parse(text)
    allowed = rp.can_fetch(url, USER_AGENT)
    delay = rp.crawl_delay(USER_AGENT)
    note = f"crawl-delay {delay}s" if delay else ""
    return ("ALLOWED" if allowed else "BLOCKED"), note


def main():
    seeds = load_seeds(SEEDS_FILE)
    print(f"Checking {len(seeds)} seed sites as '{USER_AGENT.split()[0]}'\n")
    ok = 0
    for url in seeds:
        status, note = check(url)
        ok += status == "ALLOWED"
        print(f"{status}  {url}" + (f"   [{note}]" if note else ""))
    print(f"\n{ok} allowed, {len(seeds) - ok} blocked or unreachable.")
    return 0 if ok == len(seeds) else 1


if __name__ == "__main__":
    sys.exit(main())
