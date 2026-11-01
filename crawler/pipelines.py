"""
IRIS - where crawled pages are saved.

PostgresPipeline  -> the `pages` table (only when DATABASE_URL is set, in the shell or in .env)
JsonLinesPipeline -> crawler/output/pages.jsonl (always; a backup and a file to share with the team)

Each item has action = "new" (insert) or "update" (the page changed since the last crawl).
Both pipelines give the spider the pages saved in earlier runs, so a new crawl only adds
new pages and rewrites changed ones.
"""
import json
import os
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent

# Columns the crawler can fill. Only the ones that exist in the table are written,
# so the pipeline also works with the minimal contract table pages(id, url, title, text, crawled_at).
PAGE_COLUMNS = ["url", "site", "title", "description", "language", "text", "word_count",
                "content_hash", "etag", "last_modified", "crawled_at", "updated_at"]
# Columns rewritten when a page changed (url, site and crawled_at stay as they were)
UPDATE_COLUMNS = ["title", "description", "language", "text", "word_count",
                  "content_hash", "etag", "last_modified", "updated_at"]

CREATE_PAGES_SQL = (HERE / "pages_table.sql").read_text(encoding="utf-8")

# Week 3 columns, added to a table created before them (safe to run many times)
MIGRATE_SQL = """
ALTER TABLE pages ADD COLUMN IF NOT EXISTS etag          TEXT;
ALTER TABLE pages ADD COLUMN IF NOT EXISTS last_modified TEXT;
ALTER TABLE pages ADD COLUMN IF NOT EXISTS updated_at    TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS pages_updated_at_idx ON pages (updated_at);
"""


WEEK3_COLUMNS = {"etag", "last_modified", "updated_at"}


def ensure_pages_table(cur):
    """Create the pages table if needed, and add the week 3 columns to an older table.

    The ALTER statements need an exclusive lock on `pages`, so they run only when a column is really
    missing, and they give up after 10 s instead of waiting behind another session's open transaction."""
    cur.execute("SELECT to_regclass('pages')")
    if cur.fetchone()[0] is None:
        cur.execute(CREATE_PAGES_SQL)
    elif WEEK3_COLUMNS - table_columns(cur):
        cur.execute("SET LOCAL lock_timeout = '10s'")
        cur.execute(MIGRATE_SQL)


def table_columns(cur):
    cur.execute("SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = 'pages'")
    return {row[0] for row in cur.fetchall()}


def known_pages(cur, existing):
    """Rows of url, content_hash, etag, last_modified for the pages already in the table."""
    cols = ["url"] + [c for c in ("content_hash", "etag", "last_modified") if c in existing]
    cur.execute(f"SELECT {', '.join(cols)} FROM pages")
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def database_url():
    """DATABASE_URL from the environment, or from a .env file in the repository root."""
    if os.environ.get("DATABASE_URL"):
        value = os.environ["DATABASE_URL"].strip()
        if value.startswith("DATABASE_URL="):
            value = value.split("=", 1)[1]
        return value.strip().strip('"').strip("'")
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def read_jsonl(path, deleted=None):
    """Pages of a JSON Lines file, newest record per URL (later lines replace earlier ones).
    Records with action "delete" remove the page; pass a set as `deleted` to collect those URLs."""
    pages = {}
    path = Path(path)
    if not path.exists():
        return pages
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not row.get("url"):
                continue
            if row.get("action") == "delete":
                pages.pop(row["url"], None)
                if deleted is not None:
                    deleted.add(row["url"])
            else:
                pages[row["url"]] = row
                if deleted is not None:
                    deleted.discard(row["url"])
    return pages


# --------------------------------------------------------------------------- PostgreSQL
class PostgresPipeline:
    BATCH = 25

    def __init__(self):
        self.conn = None
        self.pending = 0
        self.inserted = 0
        self.updated = 0
        self.deleted = 0

    @classmethod
    def from_crawler(cls, crawler):
        pipe = cls()
        pipe.crawler = crawler
        return pipe

    def open_spider(self, spider=None):
        spider = spider or self.crawler.spider
        if not self.crawler.settings.getbool("IRIS_USE_DB", True):
            spider.logger.info("--no-db: PostgreSQL is not used in this run.")
            return
        url = database_url()
        if not url:
            spider.logger.warning("DATABASE_URL not set -> pages are saved to JSON Lines only.")
            return
        try:
            import psycopg2
        except ImportError:
            spider.logger.warning("psycopg2 is not installed -> JSON Lines only. Run: pip install psycopg2-binary")
            return
        try:
            self.conn = psycopg2.connect(url)
        except Exception as exc:
            spider.logger.error("Cannot connect to PostgreSQL (%s) -> JSON Lines only.", exc)
            self.conn = None
            return

        with self.conn.cursor() as cur:
            ensure_pages_table(cur)
            existing = table_columns(cur)
            rows = known_pages(cur, existing)
        self.conn.commit()
        self.insert_cols = [c for c in PAGE_COLUMNS if c in existing]
        self.update_cols = [c for c in UPDATE_COLUMNS if c in existing]
        missing = [c for c in PAGE_COLUMNS if c not in existing]
        if missing:
            spider.logger.warning("pages table has no column(s) %s; they are not saved.", missing)
        spider.load_known(rows)
        spider.logger.info("PostgreSQL connected: %d pages already in the table.", len(rows))

        self.insert_sql = (f"INSERT INTO pages ({', '.join(self.insert_cols)}) "
                           f"VALUES ({', '.join(['%s'] * len(self.insert_cols))})")
        self.update_sql = (f"UPDATE pages SET {', '.join(c + ' = %s' for c in self.update_cols)} "
                           f"WHERE url = %s")

    def process_item(self, item, spider=None):
        if self.conn is None:
            return item
        with self.conn.cursor() as cur:
            if item.get("action") == "delete":
                cur.execute("DELETE FROM pages WHERE url = %s", [item["url"]])
                self.deleted += cur.rowcount
                self.pending += 1
                return item
            cur.execute("SELECT 1 FROM pages WHERE url = %s", [item["url"]])
            exists = cur.fetchone() is not None
            if exists and item.get("action") == "update":
                cur.execute(self.update_sql, [item.get(c) for c in self.update_cols] + [item["url"]])
                self.updated += 1
            elif not exists:
                cur.execute(self.insert_sql, [item.get(c) for c in self.insert_cols])
                self.inserted += 1
        self.pending += 1
        if self.pending >= self.BATCH:
            self.conn.commit()
            self.pending = 0
        return item

    def close_spider(self, spider=None):
        spider = spider or self.crawler.spider
        if self.conn is None:
            return
        self.conn.commit()
        self.conn.close()
        spider.logger.info("PostgreSQL: %d new rows inserted, %d changed rows updated, %d old rows removed.",
                           self.inserted, self.updated, self.deleted)


# --------------------------------------------------------------------------- JSON Lines
class JsonLinesPipeline:
    """Appends one JSON object per line (new and changed pages). Use --fresh to start over."""

    def __init__(self, path):
        self.path = Path(path)
        self.file = None
        self.written = 0

    @classmethod
    def from_crawler(cls, crawler):
        pipe = cls(crawler.settings.get("IRIS_JSONL_FILE", HERE / "output" / "pages.jsonl"))
        pipe.crawler = crawler
        return pipe

    def open_spider(self, spider=None):
        spider = spider or self.crawler.spider
        self.path.parent.mkdir(parents=True, exist_ok=True)
        old = read_jsonl(self.path)
        spider.load_known(old.values())
        if old:
            spider.logger.info("JSON Lines: %d pages already in %s (new and changed pages are appended).",
                               len(old), self.path)
        self.file = self.path.open("a", encoding="utf-8")

    def process_item(self, item, spider=None):
        self.file.write(json.dumps(dict(item), ensure_ascii=False) + "\n")
        self.written += 1
        return item

    def close_spider(self, spider=None):
        spider = spider or self.crawler.spider
        if self.file:
            self.file.close()
        spider.logger.info("JSON Lines: %d records written to %s", self.written, self.path)
