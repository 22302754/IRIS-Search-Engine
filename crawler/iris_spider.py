"""
IRIS - full crawler with incremental re-crawl.

Reads the start URLs from crawler/seeds.txt and the per-site rules from crawler/sites.json,
crawls every site politely (robots.txt, 1 request per second per site), extracts clean text,
skips duplicates, and hands each page to the storage pipelines (PostgreSQL + JSON Lines).

Incremental re-crawl: pages saved in earlier runs are loaded at start-up.
  * a known page whose text has not changed is counted as "unchanged" and not written again;
  * a known page whose text changed is written again as an "update" (updated_at = now);
  * a page never seen before is written as "new";
  * a known page that is now too short, a copy of another saved page, or gone (HTTP 404/410)
    is removed ("delete"), so the collection never keeps stale versions.
Leaf pages (at the depth limit, so their links are not needed) are requested with
If-None-Match / If-Modified-Since, so an unchanged page answers "304 Not Modified" with no body.
max_pages in sites.json is the target size of the collection for a site: old pages count
towards it from the start, so running again with the same limits only checks the old pages
for changes, and raising a limit adds exactly the difference as new pages.

Do not run this file directly. Run from the repository root:
    python -m crawler.run_crawl
"""
import json
import re
import time
from collections import Counter, defaultdict
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


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- site rules
class SiteRules:
    """Crawl rules for one website."""

    def __init__(self, name, host, start_url, max_pages, max_depth, allow, deny, language="unknown"):
        self.name = name
        self.host = host
        self.start_url = start_url
        self.max_pages = int(max_pages)
        self.max_depth = int(max_depth)
        self.allow = [re.compile(p) for p in allow]
        self.deny = [re.compile(p, re.IGNORECASE) for p in deny]
        self.language = language

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
            language=site.get("language", defaults.get("language", "unknown")),
        ))
    return rules


# --------------------------------------------------------------------------- download filter
class SiteLimitMiddleware:
    """Drops queued requests for NEW pages of a site that reached its size (saves time and bandwidth).
    Pages saved in earlier runs are still downloaded, so they can be checked for changes."""

    def process_request(self, request, spider=None):
        spider = spider or getattr(self, "_spider", None)
        site = request.meta.get("site")
        if site and spider is not None and not spider.wants(request.url, site):
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
        "CONCURRENT_REQUESTS": 16,
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
        self.dedup = Deduplicator()      # text fingerprints of all saved pages
        self.known = {}                  # url -> {"hash", "etag", "last_modified"} from earlier runs
        self.seen_run = set()            # URLs processed in this run
        self.known_per_site = Counter()  # pages from earlier runs, per site (counted at start)
        self.result = defaultdict(Counter)   # site -> {"new", "updated", "unchanged"}
        self.skipped = Counter()         # why pages were not saved
        self.errors = Counter()          # failed downloads per site
        self.removed_reasons = Counter() # thin / duplicate / gone
        self.started = time.time()

    # ---- called by the pipelines at start-up with the pages of earlier runs
    def load_known(self, rows):
        """rows: iterable of dicts with url, content_hash, etag, last_modified (missing keys allowed)."""
        for row in rows:
            url = row.get("url")
            if not url:
                continue
            url = canonicalize(url)
            old = self.known.get(url, {})
            self.known[url] = {
                "hash": row.get("content_hash") or old.get("hash"),
                "etag": row.get("etag") or old.get("etag"),
                "last_modified": row.get("last_modified") or old.get("last_modified"),
            }
            self.dedup.load(urls=[url], hashes=[row.get("content_hash")])

    # ---- helpers used by the middleware and the pipelines
    def site_of(self, url):
        """Name of the site whose rules accept this URL, or None."""
        for rules in self.rules:
            if rules.accepts(url):
                return rules.name
        return None

    def collection_size(self, site):
        """Pages of the site in the collection: saved in earlier runs + new in this run - removed."""
        return self.known_per_site[site] + self.result[site]["new"] - self.result[site]["deleted"]

    def site_is_full(self, site):
        """True when the site may not get any more NEW pages."""
        rules = self.rules_by_name.get(site)
        return rules is not None and self.collection_size(site) >= rules.max_pages

    def wants(self, url, site):
        """Download this URL? Old pages always (to check them); new pages only while there is room."""
        return canonicalize(url) in self.known or not self.site_is_full(site)

    # ---- start
    async def start(self):                   # Scrapy >= 2.13
        for request in self.start_requests():
            yield request

    def start_requests(self):                # older Scrapy
        self.known_per_site = Counter(self.site_of(url) for url in self.known)
        if self.known:
            self.logger.info("Incremental mode: %d pages from earlier runs will be checked for changes.",
                             len(self.known))
        for rules in self.rules:
            self.logger.info("Seed %-15s %s (collection size %d pages, depth %d)",
                             rules.name, rules.start_url, rules.max_pages, rules.max_depth)
            yield scrapy.Request(rules.start_url, callback=self.parse, errback=self.on_error,
                                 meta={"site": rules.name}, dont_filter=True)

    def make_request(self, url, site, depth, rules):
        """Request for a followed link; leaf pages already known are asked 'has it changed?'."""
        meta = {"site": site}
        headers = {}
        old = self.known.get(url)
        if old and depth >= rules.max_depth:
            if old.get("etag"):
                headers["If-None-Match"] = old["etag"]
            if old.get("last_modified"):
                headers["If-Modified-Since"] = old["last_modified"]
            if headers:
                meta["handle_httpstatus_list"] = [304]
        return scrapy.Request(url, callback=self.parse, errback=self.on_error, meta=meta, headers=headers)

    # ---- every downloaded page
    def parse(self, response):
        site = response.meta["site"]
        rules = self.rules_by_name[site]
        url = canonicalize(response.url)
        if not self.wants(url, site):
            return
        if response.status == 304:            # conditional request: page not modified
            if url not in self.seen_run:
                self.seen_run.add(url)
                self.result[site]["unchanged"] += 1
            return

        html = page_html(response)
        if html is None:
            self.skipped["not_html"] += 1
            if self.skipped["not_html"] <= 10:
                self.logger.info("Not an HTML page (Content-Type %r): %s",
                                 _header(response, "Content-Type"), response.url)
            return
        if not rules.accepts(url):             # a redirect led outside the allowed area
            self.skipped["redirect_outside"] += 1
            return
        if url in self.seen_run:               # e.g. two URLs redirecting to the same page
            self.skipped["duplicate_url"] += 1
            return
        self.seen_run.add(url)

        yield from self.save_page(response, html, url, site, rules)

        # follow links (also from unchanged pages, so new pages below them are found)
        depth = response.meta.get("depth", 0)
        if depth >= rules.max_depth:
            return
        for href in scrapy.Selector(text=html).css("a::attr(href)").getall():
            href = href.strip()
            if not href or href.startswith(("#", "mailto:", "javascript:", "tel:")):
                continue
            link = canonicalize(response.urljoin(href))
            if rules.accepts(link) and link not in self.seen_run and self.wants(link, site):
                yield self.make_request(link, site, depth + 1, rules)

    def save_page(self, response, html, url, site, rules):
        """Decide new / updated / unchanged / skipped, and yield the item to store."""
        page = extract_page(html, url)
        if page is None:
            if url in self.known:             # an old page that is now only a menu or a stub
                yield self.delete_item(url, site, "thin")
            else:
                self.skipped["thin_page"] += 1
            return
        if page["language"] == "unknown":
            page["language"] = rules.language

        old = self.known.get(url)
        if old and old.get("hash") == page["content_hash"]:
            self.result[site]["unchanged"] += 1
            return
        if not old and self.site_is_full(site):
            return
        if not self.dedup.is_new_content(page["content_hash"]):
            if old:                       # its text is now a copy of another page: drop the stale row
                yield self.delete_item(url, site, "duplicate")
            else:
                self.skipped["duplicate_text"] += 1
            return

        action = "update" if old else "new"
        self.result[site]["updated" if old else "new"] += 1
        self.known[url] = {"hash": page["content_hash"],
                           "etag": _header(response, "ETag"),
                           "last_modified": _header(response, "Last-Modified")}
        stamp = now_iso()
        page.update({
            "site": site,
            "depth": response.meta.get("depth", 0),
            "etag": self.known[url]["etag"],
            "last_modified": self.known[url]["last_modified"],
            "crawled_at": stamp,
            "updated_at": stamp,
            "action": action,
        })
        r = self.result[site]
        if action == "new" and (r["new"] % 50 == 0 or self.site_is_full(site)):
            self.logger.info("%-15s %d / %d pages in the collection (%d new this run)", site,
                             self.collection_size(site), rules.max_pages, r["new"])
        yield page

    def delete_item(self, url, site, reason):
        """Item that tells the pipelines to remove an old page from the collection."""
        self.known.pop(url, None)
        self.result[site]["deleted"] += 1
        self.removed_reasons[reason] += 1
        return {"url": url, "site": site, "action": "delete", "reason": reason, "updated_at": now_iso()}

    def on_error(self, failure):
        site = failure.request.meta.get("site", "?")
        # HttpError (404, 500 ...) is a kind of IgnoreRequest, so check it first
        if not failure.check(HttpError) and failure.check(IgnoreRequest):
            return                              # dropped on purpose (site limit, robots.txt)
        self.errors[site] += 1
        self.logger.debug("Download failed (%s): %s", site, failure.request.url)
        if failure.check(HttpError) and failure.value.response.status in (404, 410):
            url = canonicalize(failure.request.url)
            if url in self.known:               # the page no longer exists on the site
                yield self.delete_item(url, site, "gone")

    # ---- end of crawl: save statistics for the crawl report
    def closed(self, reason):
        stats = self.crawler.stats.get_stats()
        summary = {
            "finished_at": now_iso(),
            "finish_reason": reason,
            "duration_seconds": round(time.time() - self.started, 1),
            "incremental": bool(self.known),
            "sites": {
                r.name: {
                    "seed": r.start_url,
                    "max_pages": r.max_pages,
                    "max_depth": r.max_depth,
                    "new": self.result[r.name]["new"],
                    "updated": self.result[r.name]["updated"],
                    "unchanged": self.result[r.name]["unchanged"],
                    "deleted": self.result[r.name]["deleted"],
                    "known_before": self.known_per_site[r.name],
                    "collection": self.collection_size(r.name),
                    "errors": self.errors[r.name],
                }
                for r in self.rules
            },
            "skipped": dict(self.skipped),
            "removed": dict(self.removed_reasons),
            "requests": stats.get("downloader/request_count", 0),
            "responses": stats.get("downloader/response_count", 0),
            "robots_forbidden": stats.get("robotstxt/forbidden", 0),
            "status_codes": {k.rsplit("/", 1)[-1]: v for k, v in stats.items()
                             if k.startswith("downloader/response_status_count/")},
        }
        out = Path(self.settings.get("IRIS_STATS_FILE", HERE / "output" / "crawl_stats.json"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        new = sum(r["new"] for r in self.result.values())
        upd = sum(r["updated"] for r in self.result.values())
        same = sum(r["unchanged"] for r in self.result.values())
        self.logger.info("Crawl finished in %.0f s: %d new, %d updated, %d unchanged pages. Stats: %s",
                         summary["duration_seconds"], new, upd, same, out)


HTML_START = (b"<!doctype html", b"<html", b"<?xml")


def page_html(response):
    """The page as text if it is HTML, else None.
    Some servers send HTML with a missing or generic Content-Type, so the start of the body is checked too."""
    content_type = (_header(response, "Content-Type") or "").lower()
    looks_html = response.body[:1024].lstrip().lower().startswith(HTML_START)
    if "html" not in content_type and not looks_html:
        return None
    if isinstance(response, scrapy.http.TextResponse):
        return response.text
    return response.body.decode("utf-8", errors="replace")


def _header(response, name):
    value = response.headers.get(name)
    return value.decode("latin-1").strip() if value else None
