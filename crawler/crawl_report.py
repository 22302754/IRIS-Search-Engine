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


def build_report(pages_file, stats_file):
    pages = []
    if Path(pages_file).exists():
        with open(pages_file, encoding="utf-8") as fh:
            pages = [json.loads(line) for line in fh if line.strip()]
    stats = json.loads(Path(stats_file).read_text(encoding="utf-8")) if Path(stats_file).exists() else {}

    per_site = defaultdict(lambda: {"pages": 0, "words": 0})
    languages = Counter()
    for p in pages:
        s = per_site[p.get("site", "?")]
        s["pages"] += 1
        s["words"] += p.get("word_count") or len(p.get("text", "").split())
        languages[p.get("language", "unknown")] += 1

    run_sites = stats.get("sites", {})
    order = list(run_sites) + [s for s in per_site if s not in run_sites]
    total_pages = sum(s["pages"] for s in per_site.values())
    total_words = sum(s["words"] for s in per_site.values())

    out = ["# Crawl Report", ""]
    out.append(f"Generated: {datetime.now().strftime('%d %B %Y, %H:%M')} · Owner: Mohammed (Crawler)")
    out.append("")
    out.append(f"The collection holds **{total_pages:,} pages** and **{total_words:,} words** "
               f"from **{len(per_site)} sites**.")
    if stats:
        out.append(f"The last crawl took **{fmt_duration(stats.get('duration_seconds', 0))}**, "
                   f"sent {stats.get('requests', 0):,} requests and finished with reason "
                   f"`{stats.get('finish_reason', '?')}`.")
    out.append("")

    out += ["## Pages per site", "",
            "| Site | Seed URL | Pages | Avg. words / page | Total words | Page limit (per run) | Download errors (last run) |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for name in order:
        s = per_site.get(name, {"pages": 0, "words": 0})
        r = run_sites.get(name, {})
        avg = s["words"] // s["pages"] if s["pages"] else 0
        out.append(f"| {name} | {r.get('seed', '')} | {s['pages']:,} | {avg:,} | {s['words']:,} | "
                   f"{r.get('max_pages', '')} | {r.get('errors', '')} |")
    out.append(f"| **Total** | | **{total_pages:,}** | "
               f"**{(total_words // total_pages) if total_pages else 0:,}** | **{total_words:,}** | | "
               f"**{sum(r.get('errors', 0) for r in run_sites.values())}** |")
    out.append("")

    if stats:
        out += ["## Pages not saved (last run)", "", "| Reason | Pages |", "| --- | ---: |"]
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
    args = ap.parse_args(argv)
    report = build_report(args.pages, args.stats)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(report, encoding="utf-8")
    print(report)
    print(f"\nSaved to {args.out}")


if __name__ == "__main__":
    main()
