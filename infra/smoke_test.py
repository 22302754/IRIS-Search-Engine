"""
IRIS - smoke test of the running search engine: 20 queries, response time and result count.

    python3 -m infra.smoke_test                                   # local app: flask --app web.app run
    python3 -m infra.smoke_test --base-url https://iris-search.onrender.com --out docs/smoke-test.md

Uses GET /search?q= (JSON, docs/contracts.md). If /search does not exist yet, it falls back to
the HTML page /results?q= and reads the result count from the page.
Queries come from the team's evaluation set docs/test-queries.json when it exists (a plain text or
Markdown list with one query per line also works), otherwise from the 20 built-in queries below. The target is under 1 second per query (NFR-1).
"""
import argparse
import json
import re
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_MS = 1000
DEFAULT_QUERIES = [
    "inverted index", "tf idf weighting", "cosine similarity", "web crawler politeness",
    "robots.txt", "boolean retrieval", "stemming and lemmatization", "precision and recall",
    "python list comprehension", "python dictionary methods", "flask routing", "jinja templates",
    "postgresql full text search", "database index", "scrapy spider", "http caching headers",
    "css flexbox", "javascript promises", "travel books", "quotes about love",
]


def load_queries(path):
    path = Path(path)
    if not path.exists():
        return DEFAULT_QUERIES
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data.get("queries", []) if isinstance(data, dict) else data
        return [item["query"] if isinstance(item, dict) else str(item) for item in items] or DEFAULT_QUERIES
    queries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip().strip("`\"")
        if line and not line.startswith("#") and not line.startswith("|"):
            queries.append(line)
    return queries or DEFAULT_QUERIES


def fetch(url, timeout):
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "IRIS-smoke-test"}),
                                    timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except urllib.error.HTTPError as exc:
        body, status = exc.read().decode("utf-8", errors="replace"), exc.code
    except (urllib.error.URLError, TimeoutError) as exc:
        return None, str(exc), (time.perf_counter() - started) * 1000
    return status, body, (time.perf_counter() - started) * 1000


def check(base_url, queries, timeout=30):
    base_url = base_url.rstrip("/")
    mode = "json"
    status, _, _ = fetch(f"{base_url}/search?q=test", timeout)
    if status == 404:
        mode = "html"
    if status is None:
        raise SystemExit(f"Cannot reach {base_url} - is the app running?")

    rows = []
    for q in queries:
        path = "/search" if mode == "json" else "/results"
        status, body, ms = fetch(f"{base_url}{path}?q={urllib.parse.quote(q)}", timeout)
        total, top = None, ""
        if status == 200 and mode == "json":
            try:
                data = json.loads(body)
                total = data.get("total")
                top = (data.get("results") or [{}])[0].get("title", "") if data.get("results") else ""
            except json.JSONDecodeError:
                status = "bad JSON"
        elif status == 200:
            m = re.search(r"([\d,]+)\s+results?", body)
            total = int(m.group(1).replace(",", "")) if m else (0 if "No results" in body else None)
            t = re.search(r'class="result".*?<a[^>]*>(.*?)</a>', body, re.S)
            top = re.sub(r"<[^>]+>", "", t.group(1)).strip() if t else ""
        rows.append({"query": q, "status": status, "ms": ms, "total": total, "top": top})
    return mode, rows


def report(base_url, mode, rows):
    times = [r["ms"] for r in rows if r["status"] == 200]
    ok = sum(1 for r in rows if r["status"] == 200)
    fast = sum(1 for t in times if t < TARGET_MS)
    with_results = sum(1 for r in rows if r["total"])
    out = ["# Search Smoke Test", "",
           f"Run: {datetime.now().strftime('%d %B %Y, %H:%M')} · Target: `{base_url}` · "
           f"Endpoint: `{'/search (JSON)' if mode == 'json' else '/results (HTML page)'}`", ""]
    if times:
        p95 = sorted(times)[max(0, int(round(0.95 * len(times))) - 1)]
        out += [f"**{fast} of {len(rows)} queries answered in under 1 second** (median "
                f"{statistics.median(times):.0f} ms, 95th percentile {p95:.0f} ms, slowest {max(times):.0f} ms). "
                f"{ok} returned HTTP 200 and {with_results} found at least one result.", ""]
    if mode == "html":
        out += ["> `/search` is not available yet, so the HTML results page was timed instead.", ""]
    out += ["| # | Query | Status | Time (ms) | Results | First result |", "| ---: | --- | --- | ---: | ---: | --- |"]
    for i, r in enumerate(rows, 1):
        mark = "" if r["status"] == 200 and r["ms"] < TARGET_MS else " ⚠"
        total = "" if r["total"] is None else f"{r['total']:,}"
        out.append(f"| {i} | {r['query']} | {r['status']} | {r['ms']:.0f}{mark} | {total} | {r['top'][:60]} |")
    out.append("")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Time 20 queries against the IRIS search API.")
    ap.add_argument("--base-url", default="http://127.0.0.1:5000")
    ap.add_argument("--queries", default=str(ROOT / "docs" / "test-queries.json"))
    ap.add_argument("--timeout", type=float, default=30, help="seconds per request (free hosting wakes up slowly)")
    ap.add_argument("--out", default=None, help="also save the report, e.g. docs/smoke-test.md")
    args = ap.parse_args(argv)

    print(f"Waking up {args.base_url} ...", flush=True)
    fetch(args.base_url, args.timeout)          # free Render apps sleep; the first request wakes them
    mode, rows = check(args.base_url, load_queries(args.queries), args.timeout)
    text = report(args.base_url, mode, rows)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"Saved to {args.out}")


if __name__ == "__main__":
    main()
