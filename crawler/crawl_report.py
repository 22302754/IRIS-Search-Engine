"""
IRIS - turn the crawl output into a short Markdown report for the team and the final report.

Run from the repository root after a crawl:
    python -m crawler.crawl_report
It reads  crawler/output/pages.jsonl  and  crawler/output/crawl_stats.json
and writes docs/crawl-report.md
"""
import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from crawler.iris_spider import load_rules
from crawler.pipelines import database_url, read_jsonl

HERE = Path(__file__).parent
ROOT = HERE.parent

SKIP_LABELS = {
    "thin_page": "Too little text (menus, redirects, empty pages)",
    "duplicate_text": "Same text as a page already saved",
    "duplicate_url": "URL already saved",
    "not_html": "Not an HTML page",
    "redirect_outside": "Redirected outside the allowed area",
}


def fmt_duration(seconds):
    seconds = int(seconds)
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h} h {m} min {s} s" if h else f"{m} min {s} s"


def load_pages(pages_file, source="auto"):
    """The collection, from the database (when DATABASE_URL works) or from pages.jsonl.
    Returns (pages, description of the source)."""
    if source in ("auto", "db") and database_url():
        try:
            import psycopg2
            conn = psycopg2.connect(database_url(), connect_timeout=10)
            with conn.cursor() as cur:
                cur.execute("SELECT site, word_count, language FROM pages")
                rows = [{"site": s, "word_count": w, "language": l} for s, w, l in cur.fetchall()]
            conn.close()
            return rows, "the database"
        except Exception as exc:
            if source == "db":
                raise SystemExit(f"Cannot read the pages table: {exc}")
            print(f"(database not reachable: {exc}; using {pages_file})")
    return list(read_jsonl(pages_file).values()), Path(pages_file).name


def build_report(pages_file, stats_file, source="auto"):
    pages, origin = load_pages(pages_file, source)
    stats = json.loads(Path(stats_file).read_text(encoding="utf-8")) if Path(stats_file).exists() else {}

    per_site = defaultdict(lambda: {"pages": 0, "words": 0})
    languages = Counter()
    for p in pages:
        s = per_site[p.get("site", "?")]
        s["pages"] += 1
        s["words"] += p.get("word_count") or len(p.get("text", "").split())
        languages[p.get("language", "unknown")] += 1

    run_sites = stats.get("sites", {})
    # seed and target size come from the configuration, so sites missing from a partial run still show them
    try:
        config = {r.name: r for r in load_rules(HERE / "seeds.txt", HERE / "sites.json")}
    except (OSError, ValueError):
        config = {}
    order = list(config) + [s for s in list(run_sites) + list(per_site) if s not in config]
    order = list(dict.fromkeys(order))
    total_pages = sum(s["pages"] for s in per_site.values())
    total_words = sum(s["words"] for s in per_site.values())

    out = ["# Crawl Report", ""]
    out.append(f"Generated: {datetime.now().strftime('%d %B %Y, %H:%M')} · Owner: Mohammed (Crawler)")
    out.append("")
    out.append(f"Pages counted from {origin}.")
    out.append("")
    out.append(f"The collection holds **{total_pages:,} pages** and **{total_words:,} words** "
               f"from **{len(per_site)} sites**.")
    if stats and len(run_sites) < len(config):
        out.append(f"The last crawl covered only: {', '.join(run_sites)} (\"–\" = site not in the last crawl).")
    if stats:
        out.append(f"The last crawl took **{fmt_duration(stats.get('duration_seconds', 0))}**, "
                   f"sent {stats.get('requests', 0):,} requests and finished with reason "
                   f"`{stats.get('finish_reason', '?')}`.")
    out.append("")

    out += ["## Pages per site", "",
            "| Site | Seed URL | Pages | Avg. words / page | Total words | Target size | New (last run) | Updated (last run) | Unchanged (last run) | Download errors (last run) |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for name in order:
        s = per_site.get(name, {"pages": 0, "words": 0})
        r = run_sites.get(name, {})
        c = config.get(name)
        seed = r.get("seed") or (c.start_url if c else "")
        target = r.get("max_pages") or (c.max_pages if c else "")
        avg = s["words"] // s["pages"] if s["pages"] else 0
        if r:
            last = f"{r.get('new', r.get('saved', 0))} | {r.get('updated', 0)} | {r.get('unchanged', 0)} | {r.get('errors', 0)}"
        else:
            last = "– | – | – | –"
        out.append(f"| {name} | {seed} | {s['pages']:,} | {avg:,} | {s['words']:,} | {target} | {last} |")

    def total(key):
        return sum(r.get(key, 0) for r in run_sites.values())
    out.append(f"| **Total** | | **{total_pages:,}** | "
               f"**{(total_words // total_pages) if total_pages else 0:,}** | **{total_words:,}** | "
               f"**{sum(c.max_pages for c in config.values()) or total('max_pages'):,}** | **{total('new') or total('saved'):,}** | **{total('updated'):,}** | "
               f"**{total('unchanged'):,}** | **{total('errors')}** |")
    out.append("")

    if stats:
        out += ["## Pages not saved (last run)", "", "| Reason | Pages |", "| --- | ---: |"]
        labels = {"thin": "Removed: old page that is now too short (only a menu or a stub)",
                  "duplicate": "Removed: old page whose text is now a copy of another page",
                  "gone": "Removed: old page that no longer exists (HTTP 404 / 410)"}
        reasons = stats.get("removed") or {}
        if not reasons and sum(r.get("deleted", 0) for r in run_sites.values()):
            reasons = {"duplicate": sum(r.get("deleted", 0) for r in run_sites.values())}
        for key, count in reasons.items():
            out.append(f"| {labels.get(key, 'Removed: ' + key)} | {count:,} |")
        for key, count in sorted(stats.get("skipped", {}).items(), key=lambda kv: -kv[1]):
            out.append(f"| {SKIP_LABELS.get(key, key)} | {count:,} |")
        out.append(f"| Blocked by robots.txt | {stats.get('robots_forbidden', 0):,} |")
        out.append("")
        codes = stats.get("status_codes", {})
        if codes:
            out += ["## HTTP status codes (last run)", "", "| Status | Responses |", "| --- | ---: |"]
            for code, count in sorted(codes.items()):
                out.append(f"| {code} | {count:,} |")
            out.append("")

    if languages:
        out += ["## Page language", "", "| Language | Pages |", "| --- | ---: |"]
        for lang, count in languages.most_common():
            out.append(f"| {lang} | {count:,} |")
        out.append("")

    out += ["## How to reproduce", "", "```bash",
            "python -m crawler.run_crawl --fresh", "python -m crawler.crawl_report", "```", ""]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write docs/crawl-report.md from the crawl output.")
    ap.add_argument("--pages", default=str(HERE / "output" / "pages.jsonl"))
    ap.add_argument("--stats", default=str(HERE / "output" / "crawl_stats.json"))
    ap.add_argument("--out", default=str(ROOT / "docs" / "crawl-report.md"))
    ap.add_argument("--source", choices=["auto", "db", "jsonl"], default="auto",
                    help="where to count pages: the database if reachable (auto), only db, or only jsonl")
    args = ap.parse_args(argv)
    report = build_report(args.pages, args.stats, args.source)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(report, encoding="utf-8")
    print(report)
    print(f"\nSaved to {args.out}")


if __name__ == "__main__":
    main()
