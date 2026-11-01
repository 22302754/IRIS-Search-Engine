"""
IRIS - data-quality check of the crawled collection.

    python3 -m infra.check_quality                  # reads the database (or pages.jsonl) -> docs/data-quality.md
    python3 -m infra.check_quality --source jsonl --recrawl-out /tmp/recrawl.txt

Checks
  1. language unknown       - page did not get the site's default language (usually a page not refreshed since week 2)
  2. very short / very long - under 50 words or over 20,000 words
  3. template text          - the same line on 30 % or more of a site's pages (menu or footer text the cleaner missed)
  4. duplicate titles       - two or more pages of one site with exactly the same title
  5. near-duplicates        - different text that is almost the same (SimHash, 64 bits, at most 6 bits apart)
"""
import argparse
import hashlib
import re
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from crawler.pipelines import database_url, read_jsonl

ROOT = Path(__file__).resolve().parents[1]
SHORT_WORDS, LONG_WORDS = 50, 20_000
TEMPLATE_SHARE, TEMPLATE_MIN_PAGES, TEMPLATE_MIN_CHARS = 0.30, 20, 25
SIMHASH_BITS, SIMHASH_MAX_DISTANCE = 64, 6   # one changed word in a page is ~4 bits; unrelated pages ~32
SHOW = 15


# --------------------------------------------------------------------------- loading
def load_pages(source="auto", pages_file=None):
    pages_file = pages_file or ROOT / "crawler" / "output" / "pages.jsonl"
    if source in ("auto", "db") and database_url():
        try:
            import psycopg2
            conn = psycopg2.connect(database_url(), connect_timeout=10)
            with conn.cursor() as cur:
                cur.execute("SELECT url, site, title, language, word_count, text FROM pages")
                cols = [d[0] for d in cur.description]
                rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            conn.close()
            return rows, "the database"
        except Exception as exc:
            if source == "db":
                raise SystemExit(f"Cannot read the pages table: {exc}")
            print(f"(database not reachable: {exc}; using {pages_file})")
    return list(read_jsonl(pages_file).values()), Path(pages_file).name


# --------------------------------------------------------------------------- checks
def unknown_language(pages):
    return [p for p in pages if (p.get("language") or "unknown") == "unknown"]


def size_outliers(pages, short=SHORT_WORDS, long=LONG_WORDS):
    def words(p):
        return p.get("word_count") or len((p.get("text") or "").split())
    return ([p for p in pages if words(p) < short], [p for p in pages if words(p) > long])


def template_lines(pages, share=TEMPLATE_SHARE, min_pages=TEMPLATE_MIN_PAGES, min_chars=TEMPLATE_MIN_CHARS):
    """[(site, line, pages_with_line, site_pages)] for lines repeated on many pages of one site."""
    by_site = defaultdict(list)
    for p in pages:
        by_site[p.get("site") or "?"].append(p)
    found = []
    for site, site_pages in by_site.items():
        if len(site_pages) < min_pages:
            continue
        counts = Counter()
        for p in site_pages:
            counts.update({line.strip() for line in (p.get("text") or "").split("\n")
                           if len(line.strip()) >= min_chars})
        for line, n in counts.items():
            if n / len(site_pages) >= share:
                found.append((site, line, n, len(site_pages)))
    return sorted(found, key=lambda x: -x[2] / x[3])


def duplicate_titles(pages):
    groups = defaultdict(list)
    for p in pages:
        title = (p.get("title") or "").strip()
        if title:
            groups[(p.get("site") or "?", title)].append(p["url"])
    return sorted(((site, title, urls) for (site, title), urls in groups.items() if len(urls) > 1),
                  key=lambda g: -len(g[2]))


def simhash(text, bits=SIMHASH_BITS, max_shingles=3000):
    """64-bit SimHash of the page's word 3-shingles. Similar texts get hashes a few bits apart.
    Each shingle hash is written as a 64-character bit string; zip(*...) turns them into 64
    columns whose '1's are counted in C, which is ~50x faster than looping over the bits."""
    words = re.findall(r"\w+", (text or "").lower())
    shingles = sorted({" ".join(words[i:i + 3]) for i in range(max(1, len(words) - 2))})
    if len(shingles) > max_shingles:            # long pages: an even sample is enough for a fingerprint
        step = len(shingles) / max_shingles
        shingles = [shingles[int(i * step)] for i in range(max_shingles)]
    width = f"0{bits}b"
    rows = [format(int.from_bytes(hashlib.blake2b(sh.encode(), digest_size=bits // 8).digest(), "big"), width)
            for sh in shingles]
    half = len(rows) / 2
    value = 0
    for position, column in enumerate(zip(*rows)):
        if column.count("1") > half:
            value |= 1 << (bits - 1 - position)
    return value


def near_duplicates(pages, max_distance=SIMHASH_MAX_DISTANCE):
    """[(url_a, url_b, distance)] for pages whose SimHash differs in at most max_distance bits.
    Hashes are split into max_distance + 1 blocks; two hashes that differ in at most max_distance
    bits must agree on at least one whole block, so only pages sharing a block are compared."""
    hashes = [(p["url"], simhash(p.get("text"))) for p in pages if p.get("text")]
    blocks = max_distance + 1
    edges = [round(SIMHASH_BITS * k / blocks) for k in range(blocks + 1)]
    buckets = defaultdict(list)
    for i, (_, h) in enumerate(hashes):
        for block in range(blocks):
            lo, hi = edges[block], edges[block + 1]
            buckets[(block, h >> lo & ((1 << (hi - lo)) - 1))].append(i)
    pairs = set()
    for members in buckets.values():
        for x in range(len(members)):
            for y in range(x + 1, len(members)):
                i, j = members[x], members[y]
                d = bin(hashes[i][1] ^ hashes[j][1]).count("1")
                if d <= max_distance:
                    pairs.add((min(i, j), max(i, j), d))
    return sorted(((hashes[i][0], hashes[j][0], d) for i, j, d in pairs), key=lambda t: t[2])


# --------------------------------------------------------------------------- report
def build_report(pages, origin):
    started = time.time()
    unknown = unknown_language(pages)
    short, long = size_outliers(pages)
    template = template_lines(pages)
    titles = duplicate_titles(pages)
    near = near_duplicates(pages)

    out = ["# Data-Quality Report", "",
           f"Generated: {datetime.now().strftime('%d %B %Y, %H:%M')} · Owner: Mohammed (Crawler) · "
           f"{len(pages):,} pages from {origin}", "",
           "| Check | Found | What to do |", "| --- | ---: | --- |",
           f"| Language unknown | {len(unknown)} | Re-crawl the site; stale copies are refreshed or removed |",
           f"| Very short (< {SHORT_WORDS} words) | {len(short)} | Check the cleaner on these pages |",
           f"| Very long (> {LONG_WORDS:,} words) | {len(long)} | Fine for TF-IDF; mention in the report |",
           f"| Template lines (on ≥ {TEMPLATE_SHARE:.0%} of a site's pages) | {len(template)} | "
           f"Add a cleaner rule if the line is menu or footer text |",
           f"| Duplicate titles in one site | {len(titles)} groups | Usually different pages with a generic title |",
           f"| Near-duplicate pages | {len(near)} pairs | Check whether one page should be skipped |", ""]

    def section(title, rows):
        out.extend([f"## {title}", ""])
        if not rows:
            out.extend(["None.", ""])
            return
        out.extend(rows[:SHOW])
        if len(rows) > SHOW:
            out.append(f"- … and {len(rows) - SHOW} more")
        out.append("")

    section("Language unknown", [f"- {p.get('site')}: {p['url']}" for p in unknown])
    section("Very short pages", [f"- {p.get('site')}: {p.get('word_count')} words – {p['url']}" for p in short])
    section("Very long pages", [f"- {p.get('site')}: {p.get('word_count'):,} words – {p['url']}" for p in long])
    section("Template lines", [f"- {site}: on {n} of {total} pages ({n / total:.0%}) – \"{line[:100]}\""
                               for site, line, n, total in template])
    section("Duplicate titles", [f"- {site}: \"{title[:80]}\" × {len(urls)}" for site, title, urls in titles])
    section("Near-duplicate pages", [f"- {d} bits apart: {a}  ↔  {b}" for a, b, d in near])
    out.append(f"Checked in {time.time() - started:.1f} s with `python3 -m infra.check_quality`.")
    return "\n".join(out) + "\n", unknown + short


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check the quality of the crawled pages.")
    ap.add_argument("--source", choices=["auto", "db", "jsonl"], default="auto")
    ap.add_argument("--pages", default=None, help="pages.jsonl to use when not reading the database")
    ap.add_argument("--out", default=str(ROOT / "docs" / "data-quality.md"))
    ap.add_argument("--recrawl-out", default=None, help="write the URLs worth re-crawling to this file")
    args = ap.parse_args(argv)

    pages, origin = load_pages(args.source, args.pages)
    report, recrawl = build_report(pages, origin)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(report, encoding="utf-8")
    print(report)
    print(f"Saved to {args.out}")
    if args.recrawl_out:
        Path(args.recrawl_out).write_text("".join(p["url"] + "\n" for p in recrawl), encoding="utf-8")
        print(f"{len(recrawl)} URLs written to {args.recrawl_out}")


if __name__ == "__main__":
    main()
