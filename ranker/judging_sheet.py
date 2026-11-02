"""
IRIS - judging sheet for the Precision@10 evaluation (NFR-7).

    python3 -m ranker.judging_sheet                       # -> docs/judging-sheet.csv
    python3 -m ranker.judging_sheet --out my-sheet.csv

For each of the 20 queries in docs/test-queries.json it saves the top 10 results exactly as the search page
shows them (same ranking: all query words required, title bonus). The `relevant` column is left EMPTY on
purpose: two team members open each page and write 1 (relevant) or 0, using only the "relevant if" rule of the
query. Then:

    python3 -m ranker.judging_sheet --score docs/judging-sheet.csv     # Precision@10 per query and the mean
"""
import argparse
import csv
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = ["query_id", "query", "rank", "page_id", "score", "site", "title", "url", "relevant_if",
           "relevant", "judge"]


def build(out, queries_file, database_url):
    import psycopg2

    from ranker.search import search_page

    queries = json.loads(Path(queries_file).read_text(encoding="utf-8"))
    rows = []
    with psycopg2.connect(database_url) as connection:
        for q in queries:
            total, results = search_page(connection, q["query"], page=1, per_page=10)
            for position, r in enumerate(results, 1):
                rows.append({"query_id": q["id"], "query": q["query"], "rank": position, "page_id": r["id"],
                             "score": f"{r['score']:.4f}", "site": r["site"], "title": r["title"], "url": r["url"],
                             "relevant_if": q.get("relevant_if", ""), "relevant": "", "judge": ""})
            print(f"{q['id']}  {q['query']:<40} {total:>5} pages, top {len(results)} saved")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} rows to {out}. Fill the 'relevant' column with 1 or 0.")


def score(sheet):
    """Precision@10 per query (relevant results in the top 10 / 10) and the mean over the judged queries."""
    per_query = {}
    with open(sheet, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["relevant"].strip() not in ("0", "1"):
                continue
            hits, judged = per_query.get(row["query_id"], (0, 0))
            per_query[row["query_id"]] = (hits + int(row["relevant"]), judged + 1)
    if not per_query:
        sys.exit("No judged rows yet: fill the 'relevant' column with 1 or 0.")
    for query_id, (hits, judged) in sorted(per_query.items()):
        print(f"{query_id}  P@10 = {hits / 10:.1f}   ({hits} relevant of {judged} judged)")
    mean = sum(hits / 10 for hits, _ in per_query.values()) / len(per_query)
    print(f"Mean Precision@10 over {len(per_query)} queries: {mean:.3f}")
    return mean


def main(argv=None):
    ap = argparse.ArgumentParser(description="Make or score the Precision@10 judging sheet.")
    ap.add_argument("--out", default=str(ROOT / "docs" / "judging-sheet.csv"))
    ap.add_argument("--queries", default=str(ROOT / "docs" / "test-queries.json"))
    ap.add_argument("--score", metavar="SHEET", help="compute Precision@10 from a filled sheet instead")
    args = ap.parse_args(argv)
    if args.score:
        score(args.score)
        return
    from dotenv import load_dotenv

    load_dotenv()
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not set (put it in .env).")
    build(args.out, args.queries, url)


if __name__ == "__main__":
    main()
