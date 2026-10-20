"""
IRIS - run the whole data pipeline with one command.

    python3 run_pipeline.py                     # robots check -> crawl -> crawl report -> index
    python3 run_pipeline.py --skip-crawl        # only rebuild the report and the index
    python3 run_pipeline.py --only books --max-pages 20   # quick test

Steps
  1. robots.txt check of every seed            (crawler/check_robots.py)   - warning only
  2. crawl: new pages added, changed pages updated (crawler/run_crawl.py)
  3. crawl report -> docs/crawl-report.md       (crawler/crawl_report.py)
  4. index the pages                            (indexer/build.py)          - skipped until it exists

Each step runs as its own Python process, so one step's failure is reported clearly
and the remaining steps are not run.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(title, args):
    print(f"\n=== {title} ===", flush=True)
    started = time.time()
    code = subprocess.call([sys.executable, *args], cwd=ROOT)
    seconds = time.time() - started
    print(f"--- {title}: {'OK' if code == 0 else f'FAILED (exit {code})'} in {seconds:.0f} s", flush=True)
    return code, seconds


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run robots check, crawl, report and index in order.")
    ap.add_argument("--skip-robots", action="store_true")
    ap.add_argument("--skip-crawl", action="store_true")
    ap.add_argument("--skip-index", action="store_true")
    ap.add_argument("--only", default="", help="crawl only these sites, e.g. books,mdn")
    ap.add_argument("--max-pages", type=int, default=None, help="override every site's page limit")
    ap.add_argument("--fresh", action="store_true", help="start a new pages.jsonl (database is kept)")
    args = ap.parse_args(argv)

    summary = []

    if not args.skip_robots:
        code, sec = run("1/4 robots.txt check", ["crawler/check_robots.py"])
        summary.append(("robots.txt check", "OK" if code == 0 else "WARNING: a seed is blocked or unreachable", sec))

    if not args.skip_crawl:
        crawl = ["-m", "crawler.run_crawl", "--log-level", "INFO"]
        if args.only:
            crawl += ["--only", args.only]
        if args.max_pages:
            crawl += ["--max-pages", str(args.max_pages)]
        if args.fresh:
            crawl.append("--fresh")
        code, sec = run("2/4 crawl", crawl)
        summary.append(("crawl", "OK" if code == 0 else "FAILED", sec))
        if code:
            return finish(summary, 1)

    code, sec = run("3/4 crawl report", ["-m", "crawler.crawl_report"])
    summary.append(("crawl report", "OK" if code == 0 else "FAILED", sec))
    if code:
        return finish(summary, 1)

    if args.skip_index:
        summary.append(("index", "skipped (--skip-index)", 0))
    elif (ROOT / "indexer" / "build.py").exists():
        code, sec = run("4/4 index", ["-m", "indexer.build"])
        summary.append(("index", "OK" if code == 0 else "FAILED", sec))
        if code:
            return finish(summary, 1)
    else:
        print("\n=== 4/4 index ===\nindexer/build.py does not exist yet - skipped.")
        summary.append(("index", "skipped (indexer/build.py not in the repository yet)", 0))

    return finish(summary, 0)


def finish(summary, code):
    print("\n=== Pipeline summary ===")
    for step, result, seconds in summary:
        print(f"  {step:<18} {result:<55} {seconds:6.0f} s")
    return code


if __name__ == "__main__":
    sys.exit(main())
