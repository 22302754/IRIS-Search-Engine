# Deployment and Operations

Owner: Mohammed (Crawler & Infrastructure)

| Part | Where | How it is updated |
| --- | --- | --- |
| Database | Supabase, Frankfurt ([cloud-database.md](cloud-database.md)) | Weekly crawl + indexer |
| Web app (Flask) | Render, free plan, Frankfurt | Every merge into `main` is deployed automatically |
| Weekly crawl | GitHub Actions, Mondays 02:00 UTC | `.github/workflows/weekly-crawl.yml` |
| Backups | Before every weekly crawl, kept 30 days as a workflow artifact | `python3 -m infra.backup_db` |

## 1. Web app on Render

The repository already contains `render.yaml`, so Render reads the settings from it.

1. Sign in at render.com with GitHub.
2. **New → Blueprint**, choose the `IRIS-Search-Engine` repository, then **Apply**.
3. When asked for `DATABASE_URL`, paste the Supabase session pooler string (the same line as in `.env`, without `DATABASE_URL=`).
4. Wait for the first build (3–5 minutes). The app URL looks like `https://iris-search.onrender.com`.
5. Share the URL with the team and put it in the README.

Notes

- The free plan sleeps after 15 minutes without visitors; the first request then takes about a minute.
  **Open the URL a few minutes before a demo.**
- Start command: `gunicorn web.app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 60`.
- Logs: Render dashboard → `iris-search` → **Logs**.

## 2. Weekly crawl on GitHub Actions

1. GitHub repository → **Settings → Secrets and variables → Actions → New repository secret**.
2. Name `DATABASE_URL`, value = the Supabase session pooler string. Save.
3. **Actions → Weekly crawl → Run workflow** to test it once by hand (about 25 minutes).

Each run backs up the database, crawls (new pages are added, changed pages updated, and old pages that became copies, stubs or 404 are removed), writes the
crawl report, runs the indexer when `indexer/build.py` exists, and runs the data-quality check. The reports and
the backup are attached to the run for 30 days (**Actions → the run → Artifacts**). The run also keeps the free
Supabase project awake.

## 3. Backups

```bash
python3 -m infra.backup_db                         # -> backups/2026-10-21_2030/ (gzipped CSV + schema + manifest)
python3 -m infra.restore_db backups/2026-10-21_2030 --target-url postgresql://USER@localhost:5432/iris_restore
```

The restore refuses to write into non-empty tables or into the database the backup came from unless `--force`
is given, and it checks the row counts against the backup before committing.

## 4. Checks

```bash
python3 -m infra.check_quality                     # -> docs/data-quality.md
python3 -m infra.smoke_test --base-url https://iris-search.onrender.com --out docs/smoke-test.md
```

The smoke test sends the 20 test queries (from `docs/test-queries.md` when it exists) and reports the response
time of each against the 1-second target (NFR-1).
