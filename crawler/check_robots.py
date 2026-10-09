"""
IRIS - robots.txt checker for the proposed seed sites.

For every URL in crawler/seeds.txt it downloads the site's robots.txt and
reports whether our crawler is allowed to fetch that URL.

Run (from the repository root):
    python crawler/check_robots.py
"""
import sys
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

USER_AGENT = "IRIS-StudentCrawler"
SEEDS_FILE = Path(__file__).with_name("seeds.txt")


def load_seeds(path):
    seeds = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            seeds.append(line)
    return seeds


def check(url):
    parts = urlparse(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    rp = RobotFileParser(robots_url)
    try:
        rp.read()
    except Exception as exc:  # network error, timeout, etc.
        return robots_url, None, None, f"could not read robots.txt ({exc})"
    allowed = rp.can_fetch(USER_AGENT, url)
    delay = rp.crawl_delay(USER_AGENT)
    return robots_url, allowed, delay, ""


def main():
    seeds = load_seeds(SEEDS_FILE)
    print(f"Checking {len(seeds)} seed sites as user-agent '{USER_AGENT}'\n")
    blocked = 0
    for url in seeds:
        robots_url, allowed, delay, err = check(url)
        if err:
            status = "ERROR  "
            blocked += 1
        elif allowed:
            status = "ALLOWED"
        else:
            status = "BLOCKED"
            blocked += 1
        extra = f" (crawl-delay {delay}s)" if delay else ""
        print(f"{status}  {url}{extra}")
        if err:
            print(f"         {err}")
    print(f"\n{len(seeds) - blocked} allowed, {blocked} blocked or unreachable.")
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
