"""
IRIS - load a pages.jsonl file into the PostgreSQL `pages` table.

Teammates use this to get Mohammed's crawl into their own local database
without crawling again. Pages that are already in the table are skipped.

Run from the repository root (DATABASE_URL must be set in the shell or in .env):
    python -m crawler.load_jsonl crawler/output/pages.jsonl
"""
import argparse
import json
import sys

from crawler.pipelines import PAGE_COLUMNS, database_url, ensure_pages_table


def main(argv=None):
    ap = argparse.ArgumentParser(description="Load pages.jsonl into the pages table.")
    ap.add_argument("file", help="path to pages.jsonl")
    args = ap.parse_args(argv)

    url = database_url()
    if not url:
        sys.exit("DATABASE_URL is not set. Add it to .env, e.g. "
                 "DATABASE_URL=postgresql://postgres:password@localhost:5432/iris")
    import psycopg2

    conn = psycopg2.connect(url)
    cur = conn.cursor()
    ensure_pages_table(cur)
    cur.execute("SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = 'pages'")
    existing = {r[0] for r in cur.fetchall()}
    columns = [c for c in PAGE_COLUMNS if c in existing]
    cur.execute("SELECT url FROM pages")
    known = {r[0] for r in cur.fetchall()}

    sql = f"INSERT INTO pages ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(columns))})"
    added = skipped = 0
    with open(args.file, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row["url"] in known:
                skipped += 1
                continue
            cur.execute(sql, [row.get(c) for c in columns])
            known.add(row["url"])
            added += 1
    conn.commit()
    cur.execute("SELECT count(*) FROM pages")
    total = cur.fetchone()[0]
    conn.close()
    print(f"Added {added} pages, skipped {skipped} already in the table. The table now has {total} pages.")


if __name__ == "__main__":
    main()
