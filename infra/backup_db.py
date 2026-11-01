"""
IRIS - back up the database to a dated folder.

    python3 -m infra.backup_db                    # -> backups/2026-10-21_2030/
    python3 -m infra.backup_db --out /some/folder

Each table (pages, terms, postings, page_norms, index_state - those that exist) is saved as a gzipped CSV
with PostgreSQL's COPY, so it needs no pg_dump and works with any PostgreSQL version.
The folder also holds schema.sql and manifest.json (row counts, date, source database).
Restore with:  python3 -m infra.restore_db backups/<folder>
"""
import argparse
import gzip
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from infra.db import SCHEMA_SQL, ROOT, TABLES, connect, describe, table_exists


def backup(out_root, url=None):
    started = time.time()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
    folder = Path(out_root) / stamp
    folder.mkdir(parents=True, exist_ok=True)

    conn = connect(url)
    manifest = {"created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "source": describe(url), "tables": {}}
    with conn.cursor() as cur:
        for table in TABLES:
            if not table_exists(cur, table):
                continue
            path = folder / f"{table}.csv.gz"
            with gzip.open(path, "wt", encoding="utf-8", newline="") as fh:
                cur.copy_expert(f"COPY (SELECT * FROM {table} ORDER BY 1) TO STDOUT WITH CSV HEADER", fh)
            cur.execute(f"SELECT count(*) FROM {table}")
            rows = cur.fetchone()[0]
            manifest["tables"][table] = {"rows": rows, "file": path.name, "bytes": path.stat().st_size}
            print(f"  {table:<11} {rows:>9,} rows  {path.stat().st_size / 1e6:6.1f} MB")
    conn.close()

    (folder / "schema.sql").write_text(SCHEMA_SQL, encoding="utf-8")
    manifest["seconds"] = round(time.time() - started, 1)
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Backup of {manifest['source']} saved to {folder} in {manifest['seconds']} s")
    return folder


def main(argv=None):
    ap = argparse.ArgumentParser(description="Back up the IRIS database to gzipped CSV files.")
    ap.add_argument("--out", default=str(ROOT / "backups"), help="folder that receives the dated backup")
    args = ap.parse_args(argv)
    backup(args.out)


if __name__ == "__main__":
    main()
