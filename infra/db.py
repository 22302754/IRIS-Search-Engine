"""
IRIS - small database helpers shared by the infrastructure scripts (and free for the indexer to use).

    from infra.db import connect, bulk_insert, table_exists

    with connect() as conn, conn.cursor() as cur:
        bulk_insert(cur, "postings", ["term_id", "page_id", "tf"], rows)   # 1,000 rows per round trip

connect() reads DATABASE_URL from the shell or from .env, like the crawler.
"""
import sys
from pathlib import Path
from urllib.parse import urlsplit

from crawler.pipelines import database_url

ROOT = Path(__file__).resolve().parents[1]

# The team schema (pages + index tables + index_state) lives in docs/schema.sql, owned by Software Engineer #1.
SCHEMA_SQL = (ROOT / "docs" / "schema.sql").read_text(encoding="utf-8")

# Tables in dependency order (parents first)
TABLES = ["pages", "terms", "postings", "page_norms", "index_state"]


def connect(url=None):
    """Open a psycopg2 connection to DATABASE_URL (or the given URL); exits with a clear message if unset."""
    url = url or database_url()
    if not url:
        sys.exit("DATABASE_URL is not set. Put it in .env, e.g.\n"
                 "DATABASE_URL=postgresql://postgres:password@localhost:5432/iris")
    import psycopg2
    return psycopg2.connect(url)


def describe(url=None):
    """Host and database name of a connection string, without user or password (safe to print)."""
    parts = urlsplit(url or database_url() or "")
    host = parts.hostname or "localhost"
    if "host=" in parts.query and not parts.hostname:
        host = parts.query.split("host=", 1)[1].split("&", 1)[0]
    return f"{host}/{parts.path.lstrip('/') or 'postgres'}"


def table_exists(cur, name):
    cur.execute("SELECT to_regclass(%s)", [name])
    return cur.fetchone()[0] is not None


def bulk_insert(cur, table, columns, rows, page_size=1000):
    """Insert many rows with one statement per `page_size` rows (fast on a cloud database)."""
    from psycopg2.extras import execute_values
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s"
    execute_values(cur, sql, rows, page_size=page_size)
