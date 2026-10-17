"""
IRIS - full crawler.

Reads the start URLs from crawler/seeds.txt and the per-site rules from crawler/sites.json,
crawls every site politely (robots.txt, 1 request per second per site), extracts clean text,
skips duplicates, and hands each page to the storage pipelines (PostgreSQL + JSON Lines).

Do not run this file directly. Run from the repository root:
    python -m crawler.run_crawl
"""
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import scrapy
from scrapy.exceptions import IgnoreRequest
from scrapy.spidermiddlewares.httperror import HttpError

from crawler.cleaner import canonicalize, extract_page
from crawler.dedupe import Deduplicator

HERE = Path(__file__).parent
USER_AGENT = "IRIS-StudentCrawler/0.1 (CIU capstone project; +https://github.com/22302754/IRIS-Search-Engine)"


# --------------------------------------------------------------------------- site rules
class SiteRules:
    """Crawl rules for one website."""

    def __init__(self, name, host, start_url, max_pages, max_depth, allow, deny):
        self.name = name
        self.host = host
        self.start_url = start_url
        self.max_pages = int(max_pages)
        self.max_depth = int(max_depth)
        self.allow = [re.compile(p) for p in allow]
        self.deny = [re.compile(p, re.IGNORECASE) for p in deny]

    def accepts(self, url):
        """True if the URL is on this site and its path is allowed."""
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if parts.port and parts.port not in (80, 443):
            host = f"{host}:{parts.port}"
        if parts.scheme not in ("http", "https") or host != self.host:
            return False
        path = parts.path or "/"
        if any(p.search(path) for p in self.deny):
            return False
        return any(p.search(path) for p in self.allow)


def load_rules(seeds_file, sites_file, only=None, max_pages=None):
    """Build one SiteRules per seed URL. `only` limits to some site names; `max_pages` overrides every limit."""
    config = json.loads(Path(sites_file).read_text(encoding="utf-8"))
    defaults = config.get("defaults", {})
    by_host = {s["host"].lower(): s for s in config.get("sites", [])}

    rules = []
    for line in Path(seeds_file).read_text(encoding="utf-8").splitlines():
        seed = line.strip()
        if not seed or seed.startswith("#"):
            continue
        parts = urlsplit(seed)
        host = (parts.hostname or "").lower()
        if parts.port and parts.port not in (80, 443):
            host = f"{host}:{parts.port}"
        site = by_host.get(host, {})
        name = site.get("name", host)
        if only and name not in only:
            continue
        allow = site.get("allow") or ["^" + re.escape(parts.path or "/")]
        rules.append(SiteRules(
            name=name,
            host=host,
            start_url=seed,
            max_pages=max_pages or site.get("max_pages", defaults.get("max_pages", 200)),
            max_depth=site.get("max_depth", defaults.get("max_depth", 3)),
            allow=allow,
            deny=defaults.get("deny", []) + site.get("deny", []),
        ))
    return rules


# --------------------------------------------------------------------------- download filter
class SiteLimitMiddleware:
    """Drops queued requests of a site that already reached its page limit (saves time and bandwidth)."""

    def process_request(self, request, spider=None):
        spider = spider or getattr(self, "_spider", None)
        site = request.meta.get("site")
        if site and spider is not None and spider.site_is_full(site):
            raise IgnoreRequest(f"site limit reached: {site}")
        return None

    @classmethod
    def from_crawler(cls, crawler):
        mw = cls()
        crawler.signals.connect(mw._on_open, signal=scrapy.signals.spider_opened)
        return mw

    def _on_open(self, spider):
        self._spider = spider


# --------------------------------------------------------------------------- spider
class IrisSpider(scrapy.Spider):
    name = "iris"

    custom_settings = {
        # politeness
        "ROBOTSTXT_OBEY": True,
        "USER_AGENT": USER_AGENT,
        "DOWNLOAD_DELAY": 1.0,
        "CONCURRENT_REQUESTS": 8,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        # robustness
        "DOWNLOAD_TIMEOUT": 20,
        "DOWNLOAD_MAXSIZE": 5 * 1024 * 1024,
        "RETRY_TIMES": 2,
        # breadth-first: pages close to the seed first
        "DEPTH_PRIORITY": 1,
        "SCHEDULER_DISK_QUEUE": "scrapy.squeues.PickleFifoDiskQueue",
        "SCHEDULER_MEMORY_QUEUE": "scrapy.squeues.FifoMemoryQueue",
        "DOWNLOADER_MIDDLEWARES": {"crawler.iris_spider.SiteLimitMiddleware": 50},
        "ITEM_PIPELINES": {
            "crawler.pipelines.PostgresPipeline": 300,
            "crawler.pipelines.JsonLinesPipeline": 400,
        },
        "LOG_LEVEL": "INFO",
    }

    def __init__(self, seeds=None, sites=None, only=None, max_pages=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        only = set(only.split(",")) if isinstance(only, str) and only else only
        self.rules = load_rules(seeds or HERE / "seeds.txt", sites or HERE / "sites.json",
                                only=only, max_pages=int(max_pages) if max_pages else None)
        self.rules_by_name = {r.name: r for r in self.rules}
        self.dedup = Deduplicator()          # filled with old pages by the pipelines at start
        self.saved = Counter()               # pages saved this run, per site
        self.skipped = Counter()             # why pages were not saved
        self.errors = Counter()              # failed downloads per site
        self.words = Counter()
        self.started = time.time()

    # ---- helpers used by the middleware and the pipelines
    def site_is_full(self, site):
        rules = self.rules_by_name.get(site)
        return rules is not None and self.saved[site] >= rules.max_pages

    # ---- start
    async def start(self):                   # Scrapy >= 2.13
        for request in self.start_requests():
            yield request

    def start_requests(self):                # older Scrapy
        for rules in self.rules:
            self.logger.info("Seed %-12s %s (max %d pages, depth %d)",
                             rules.name, rules.start_url, rules.max_pages, rules.max_depth)
            yield scrapy.Request(rules.start_url, callback=self.parse, errback=self.on_error,
                                 meta={"site": rules.name}, dont_filter=True)

    # ---- every downloaded page
    def parse(self, response):
        site = response.meta["site"]
        rules = self.rules_by_name[site]
        if self.site_is_full(site):
            return

        content_type = response.headers.get("Content-Type", b"").decode("latin-1").lower()
        if "html" not in content_type:
            self.skipped["not_html"] += 1
            return

        url = canonicalize(response.url)
        if not rules.accepts(url):             # a redirect led outside the allowed area
            self.skipped["redirect_outside"] += 1
            return

        if not self.dedup.is_new_url(url):
            self.skipped["duplicate_url"] += 1
        else:
            page = extract_page(response.text, url)
            if page is None:
                self.skipped["thin_page"] += 1
            elif not self.dedup.is_new_content(page["content_hash"]):
                self.skipped["duplicate_text"] += 1
            else:
                self.saved[site] += 1
                self.words[site] += page["word_count"]
                page["site"] = site
                page["depth"] = response.meta.get("depth", 0)
                page["crawled_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                if self.saved[site] % 50 == 0 or self.saved[site] == rules.max_pages:
                    self.logger.info("%-12s %d / %d pages saved", site, self.saved[site], rules.max_pages)
                yield page

        # follow links (also from already-saved pages, so a second run can go deeper)
        if response.meta.get("depth", 0) >= rules.max_depth or self.site_is_full(site):
            return
        for href in response.css("a::attr(href)").getall():
            href = href.strip()
            if not href or href.startswith(("#", "mailto:", "javascript:", "tel:")):
                continue
            link = canonicalize(response.urljoin(href))
            if rules.accepts(link):
                yield scrapy.Request(link, callback=self.parse, errback=self.on_error, meta={"site": site})

    def on_error(self, failure):
        site = failure.request.meta.get("site", "?")
        # HttpError (404, 500 ...) is a kind of IgnoreRequest, so check it first
        if not failure.check(HttpError) and failure.check(IgnoreRequest):
            return                              # dropped on purpose (site limit, robots.txt)
        self.errors[site] += 1
        self.logger.debug("Download failed (%s): %s", site, failure.request.url)

    # ---- end of crawl: save statistics for the crawl report
    def closed(self, reason):
        stats = self.crawler.stats.get_stats()
        summary = {
            "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "finish_reason": reason,
            "duration_seconds": round(time.time() - self.started, 1),
            "sites": {
                r.name: {
                    "seed": r.start_url,
                    "max_pages": r.max_pages,
                    "max_depth": r.max_depth,
                    "saved": self.saved[r.name],
                    "words": self.words[r.name],
                    "errors": self.errors[r.name],
                }
                for r in self.rules
            },
            "skipped": dict(self.skipped),
            "requests": stats.get("downloader/request_count", 0),
            "responses": stats.get("downloader/response_count", 0),
            "robots_forbidden": stats.get("robotstxt/forbidden", 0),
            "status_codes": {k.rsplit("/", 1)[-1]: v for k, v in stats.items()
                             if k.startswith("downloader/response_status_count/")},
        }
        out = Path(self.settings.get("IRIS_STATS_FILE", HERE / "output" / "crawl_stats.json"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        total = sum(self.saved.values())
        self.logger.info("Crawl finished: %d new pages saved in %.0f s. Stats: %s",
                         total, summary["duration_seconds"], out)
