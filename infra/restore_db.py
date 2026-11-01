"""
IRIS - restore a backup made by infra/backup_db.py.

    python3 -m infra.restore_db backups/2026-10-21_2030                     # into DATABASE_URL
    python3 -m infra.restore_db backups/2026-10-21_2030 --target-url postgresql://...@localhost:5432/iris_restore

Safety rules
  * the target tables must be empty, unless you add --force (then they are emptied first);
  * restoring into the same database the backup came from also needs --force.
After loading, the row counts are compared with the backup's manifest.
"""
import argparse
import gzip
import json
import sys
from pathlib import Path

from infra.db import TABLES, connect, describe, table_exists


def restore(folder, url=None, force=False):
    folder = Path(folder)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    target = describe(url)
    if target == manifest["source"] and not force:
        sys.exit(f"Refusing to restore into the database the backup came from ({target}). Add --force if you mean it.")

    tables = [t for t in TABLES if t in manifest["tables"]]
    conn = connect(url)
    with conn.cursor() as cur:
        cur.execute((folder / "schema.sql").read_text(encoding="utf-8"))   # creates missing tables only
        not_empty = []
        for table in tables:
            cur.execute(f"SELECT count(*) FROM {table}")
            if cur.fetchone()[0]:
                not_empty.append(table)
        if not_empty and not force:
            conn.rollback()
            sys.exit(f"Target tables are not empty: {', '.join(not_empty)}. Add --force to replace their contents.")
        if not_empty:
            cur.execute(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE")

        for table in tables:
            path = folder / manifest["tables"][table]["file"]
            with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
                header = fh.readline().strip()
                fh.seek(0)
                cur.copy_expert(f"COPY {table} ({header}) FROM STDIN WITH CSV HEADER", fh)
            if table_exists(cur, table) and table in ("pages", "terms"):
                cur.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                            f"COALESCE((SELECT max(id) FROM {table}), 1))")

        ok = True
        for table in tables:
            cur.execute(f"SELECT count(*) FROM {table}")
            got, want = cur.fetchone()[0], manifest["tables"][table]["rows"]
            ok &= got == want
            print(f"  {table:<11} {got:>9,} rows  {'OK' if got == want else f'EXPECTED {want:,}'}")
    if not ok:
        conn.rollback()
        conn.close()
        sys.exit("Row counts do not match the backup - nothing was changed.")
    conn.commit()
    conn.close()
    print(f"Restored {folder.name} into {target}.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Restore an IRIS database backup.")
    ap.add_argument("folder", help="backup folder, e.g. backups/2026-10-21_2030")
    ap.add_argument("--target-url", default=None, help="database to restore into (default: DATABASE_URL)")
    ap.add_argument("--force", action="store_true", help="replace existing rows / allow same database")
    args = ap.parse_args(argv)
    restore(args.folder, args.target_url, args.force)


if __name__ == "__main__":
    main()
