"""
IRIS - load a pages.jsonl file into the PostgreSQL `pages` table.

Teammates use this to get Mohammed's crawl into their own database (local or cloud)
without crawling again. New pages are inserted, pages whose text changed are updated,
and identical pages are skipped, so it is safe to run again with a newer file.

Run from the repository root (DATABASE_URL must be set in the shell or in .env):
    python -m crawler.load_jsonl crawler/output/pages.jsonl
"""
import argparse
import sys
import time

from crawler.pipelines import (PAGE_COLUMNS, UPDATE_COLUMNS, database_url, ensure_pages_table,
                               read_jsonl, table_columns)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Load pages.jsonl into the pages table.")
    ap.add_argument("file", help="path to pages.jsonl")
    args = ap.parse_args(argv)

    url = database_url()
    if not url:
        sys.exit("DATABASE_URL is not set. Add it to .env, e.g. "
                 "DATABASE_URL=postgresql://postgres:password@localhost:5432/iris")
    import psycopg2
    from psycopg2.extras import execute_values

    started = time.time()
    deleted = set()
    pages = read_jsonl(args.file, deleted)     # newest record per URL
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    ensure_pages_table(cur)
    existing = table_columns(cur)
    insert_cols = [c for c in PAGE_COLUMNS if c in existing]
    update_cols = [c for c in UPDATE_COLUMNS if c in existing]
    has_hash = "content_hash" in existing
    cur.execute(f"SELECT url, {'content_hash' if has_hash else 'NULL'} FROM pages")
    in_table = dict(cur.fetchall())

    new_rows, changed = [], []
    for page_url, row in pages.items():
        if page_url not in in_table:
            new_rows.append([row.get(c) for c in insert_cols])
        elif has_hash and row.get("content_hash") and in_table[page_url] != row["content_hash"]:
            changed.append([row.get(c) for c in update_cols] + [page_url])

    if new_rows:                               # one round trip per 500 rows: fast even on a cloud server
        execute_values(cur, f"INSERT INTO pages ({', '.join(insert_cols)}) VALUES %s", new_rows, page_size=500)
    removed = [[u] for u in deleted if u in in_table]
    if removed:                                # pages the crawler removed (stub, copy or gone)
        cur.executemany("DELETE FROM pages WHERE url = %s", removed)
    if changed:
        cur.executemany(f"UPDATE pages SET {', '.join(c + ' = %s' for c in update_cols)} WHERE url = %s", changed)
    conn.commit()
    cur.execute("SELECT count(*) FROM pages")
    total = cur.fetchone()[0]
    conn.close()
    same = len(pages) - len(new_rows) - len(changed)
    print(f"Added {len(new_rows)} pages, updated {len(changed)} changed pages, removed {len(removed)} old pages, "
          f"skipped {same} unchanged. "
          f"The table now has {total} pages ({time.time() - started:.1f} s).")


if __name__ == "__main__":
    main()
