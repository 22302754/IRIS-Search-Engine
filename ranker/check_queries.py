"""Check the 20 test queries against the real index.

    python3 -m ranker.check_queries                    # uses DATABASE_URL from .env
    python3 -m ranker.check_queries --out docs/test-queries-check.md

For every query in docs/test-queries.json it reports:
  * relevant pages in the collection: pages whose URL contains one of `relevant_url_parts`
    (0 means the query has no known relevant page in our collection -> replace or fix it);
  * best rank: the position of the first of those pages in the top 10 of rank() ("-" = not in top 10);
  * the time rank() took.

This is a coverage check, not the evaluation: Precision@10 still needs people to judge the top 10.
Exit code 1 if any query has no relevant page in the collection.
"""
import argparse
import json
import os
import sys
import time
from contextlib import closing
from pathlib import Path

from dotenv import load_dotenv

from ranker.rank import rank

ROOT = Path(__file__).resolve().parents[1]


def find_relevant(cursor, url_parts):
    cursor.execute(
        "SELECT id, url FROM pages WHERE url LIKE ANY(%s) ORDER BY id",
        ([f"%{part.replace('%', chr(92) + '%').replace('_', chr(92) + '_')}%" for part in url_parts],),
    )
    return cursor.fetchall()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check the test queries against the index.")
    parser.add_argument("--queries", default=str(ROOT / "docs" / "test-queries.json"))
    parser.add_argument("--out", help="also write the table to this Markdown file")
    args = parser.parse_args(argv)

    load_dotenv()
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not set (add it to .env).")
    import psycopg2

    queries = json.loads(Path(args.queries).read_text(encoding="utf-8"))
    lines = ["| ID | Query | Relevant pages in collection | Best rank in top 10 | Time (ms) | Top result |",
             "| --- | --- | ---: | ---: | ---: | --- |"]
    missing = []
    with closing(psycopg2.connect(url)) as conn, conn.cursor() as cur:
        for q in queries:
            relevant = find_relevant(cur, q["relevant_url_parts"])
            relevant_ids = {pid for pid, _ in relevant}
            start = time.perf_counter()
            results = rank(q["query"], k=10, connection=conn)
            ms = (time.perf_counter() - start) * 1000
            best = next((i for i, (pid, _) in enumerate(results, 1) if pid in relevant_ids), None)
            top = ""
            if results:
                cur.execute("SELECT url FROM pages WHERE id = %s", (results[0][0],))
                top = cur.fetchone()[0]
            if not relevant:
                missing.append(q["id"])
            lines.append(f"| {q['id']} | {q['query']} | {len(relevant)} | {best or '-'} | {ms:.0f} | {top} |")

    table = "\n".join(lines)
    print(table)
    print(f"\nQueries with no relevant page in the collection: {', '.join(missing) or 'none'}")
    if args.out:
        Path(args.out).write_text(table + "\n", encoding="utf-8")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
