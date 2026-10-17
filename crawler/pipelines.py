"""
IRIS - where crawled pages are saved.

PostgresPipeline  -> the `pages` table (only when DATABASE_URL is set, in the shell or in .env)
JsonLinesPipeline -> crawler/output/pages.jsonl (always; a backup and a file to share with the team)

Both load the pages saved in earlier runs into the spider's duplicate filter,
so a second crawl only adds new pages.
"""
import json
import os
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent

# Columns the crawler can fill. Only the ones that exist in the table are written,
# so the pipeline also works with the minimal contract table pages(id, url, title, text, crawled_at).
PAGE_COLUMNS = ["url", "site", "title", "description", "language", "text",
                "word_count", "content_hash", "crawled_at"]

CREATE_PAGES_SQL = (HERE / "pages_table.sql").read_text(encoding="utf-8") \
    if (HERE / "pages_table.sql").exists() else ""


def ensure_pages_table(cur):
    """Create the pages table only if it does not exist yet (never touches the team's own table)."""
    cur.execute("SELECT to_regclass('pages')")
    if cur.fetchone()[0] is None:
        cur.execute(CREATE_PAGES_SQL)


def database_url():
    """DATABASE_URL from the environment, or from a .env file in the repository root."""
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


# --------------------------------------------------------------------------- PostgreSQL
class PostgresPipeline:
    BATCH = 25

    def __init__(self):
        self.conn = None
        self.columns = []
        self.pending = 0
        self.inserted = 0

    def open_spider(self, spider=None):
        spider = spider or self.spider
        url = database_url()
        if not url:
            spider.logger.warning("DATABASE_URL not set -> pages are saved to JSON Lines only.")
            return
        try:
            import psycopg2
        except ImportError:
            spider.logger.warning("psycopg2 is not installed -> pages are saved to JSON Lines only. "
                                  "Run: pip install psycopg2-binary")
            return
        try:
            self.conn = psycopg2.connect(url)
        except Exception as exc:
            spider.logger.error("Cannot connect to PostgreSQL (%s) -> JSON Lines only.", exc)
            self.conn = None
            return

        with self.conn.cursor() as cur:
            ensure_pages_table(cur)
            cur.execute("SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = current_schema() AND table_name = 'pages'")
            existing = {row[0] for row in cur.fetchall()}
            self.columns = [c for c in PAGE_COLUMNS if c in existing]
            missing = [c for c in PAGE_COLUMNS if c not in existing]
            if missing:
                spider.logger.warning("pages table has no column(s) %s; they are not saved.", missing)

            hash_col = "content_hash" if "content_hash" in existing else "NULL"
            cur.execute(f"SELECT url, {hash_col} FROM pages")
            rows = cur.fetchall()
        self.conn.commit()
        spider.dedup.load(urls=(r[0] for r in rows), hashes=(r[1] for r in rows))
        spider.logger.info("PostgreSQL connected: %d pages already in the table.", len(rows))

        cols = ", ".join(self.columns)
        marks = ", ".join(["%s"] * len(self.columns))
        self.insert_sql = f"INSERT INTO pages ({cols}) VALUES ({marks})"

    def process_item(self, item, spider=None):
        if self.conn is None:
            return item
        with self.conn.cursor() as cur:
            # check first, so it also works if the team's table has no UNIQUE constraint on url
            cur.execute("SELECT 1 FROM pages WHERE url = %s", [item["url"]])
            if cur.fetchone() is None:
                cur.execute(self.insert_sql, [item.get(c) for c in self.columns])
                self.inserted += 1
        self.pending += 1
        if self.pending >= self.BATCH:
            self.conn.commit()
            self.pending = 0
        return item

    def close_spider(self, spider=None):
        spider = spider or self.spider
        if self.conn is None:
            return
        self.conn.commit()
        self.conn.close()
        spider.logger.info("PostgreSQL: %d new rows inserted into pages.", self.inserted)

    @classmethod
    def from_crawler(cls, crawler):
        pipe = cls()
        pipe.crawler = crawler
        return pipe

    @property
    def spider(self):
        return self.crawler.spider


# --------------------------------------------------------------------------- JSON Lines
class JsonLinesPipeline:
    """Appends one JSON object per line. Delete the file (or use --fresh) to start over."""

    def __init__(self, path):
        self.path = Path(path)
        self.file = None
        self.written = 0

    @classmethod
    def from_crawler(cls, crawler):
        pipe = cls(crawler.settings.get("IRIS_JSONL_FILE", HERE / "output" / "pages.jsonl"))
        pipe.crawler = crawler
        return pipe

    def _spider(self, spider):
        return spider or getattr(self.crawler, "spider", None)

    def open_spider(self, spider=None):
        spider = self._spider(spider)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        urls, hashes = [], []
        if self.path.exists():
            with self.path.open(encoding="utf-8") as fh:
                for line in fh:
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    urls.append(row.get("url"))
                    hashes.append(row.get("content_hash"))
        spider.dedup.load(urls=urls, hashes=hashes)
        if urls:
            spider.logger.info("JSON Lines: %d pages already in %s (new pages are appended).",
                               len(urls), self.path)
        self.file = self.path.open("a", encoding="utf-8")

    def process_item(self, item, spider=None):
        self.file.write(json.dumps(dict(item), ensure_ascii=False) + "\n")
        self.written += 1
        return item

    def close_spider(self, spider=None):
        spider = self._spider(spider)
        if self.file:
            self.file.close()
        spider.logger.info("JSON Lines: %d new pages written to %s", self.written, self.path)
