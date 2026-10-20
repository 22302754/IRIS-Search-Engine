# Shared Cloud Database

Owner: Mohammed (Crawler & Infrastructure)

One PostgreSQL database in the cloud that the whole team (and the final demo) uses, so everyone
searches the same pages and the same index. Free tier, no credit card.

## Which service

| Service | Free storage | Notes |
| --- | --- | --- |
| **Supabase** (recommended) | 500 MB | Web table viewer and SQL editor; pauses after 7 days without use (one click to resume) |
| Neon | 0.5 GB | Pure PostgreSQL; sleeps when idle and wakes on the first query |

Expected size: about 4,300 pages (≈ 50 MB of text) plus the index (`terms`, `postings`, `page_norms`,
roughly 100–200 MB). Both free tiers are enough.

## Set up (Supabase)

1. Sign in at supabase.com and create a new project named `iris` in the region closest to Cyprus
   (Frankfurt, `eu-central-1`). Save the database password in a password manager.
2. Open **Connect** (top of the project page) and copy the **Session pooler** connection string.
   It looks like
   `postgresql://postgres.<project-ref>:<password>@aws-0-eu-central-1.pooler.supabase.com:5432/postgres`.
   Use the pooler string: the direct connection needs IPv6, which many home and university networks lack.
3. Put it in your own `.env` file in the repository root (never in Git, never in the group chat):

   ```
   DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-eu-central-1.pooler.supabase.com:5432/postgres
   ```

4. Load the collection (creates the `pages` table if needed; safe to run again later):

   ```bash
   python3 -m crawler.load_jsonl crawler/output/pages.jsonl
   ```

5. Lock the tables against Supabase's public web API (our Python code connects as the database owner,
   so it is not affected). In **SQL Editor** run:

   ```sql
   ALTER TABLE pages ENABLE ROW LEVEL SECURITY;
   -- after SE #1 creates them:
   ALTER TABLE terms      ENABLE ROW LEVEL SECURITY;
   ALTER TABLE postings   ENABLE ROW LEVEL SECURITY;
   ALTER TABLE page_norms ENABLE ROW LEVEL SECURITY;
   ```

6. Check it:

   ```sql
   SELECT site, count(*) FROM pages GROUP BY site ORDER BY site;
   ```

## Sharing with the team

- Send the `DATABASE_URL` line to each teammate **in a private message**, not in the group and not in Git.
- Each teammate puts it in their own `.env`. Nothing else changes: the crawler, `load_jsonl`, the indexer
  and the Flask app all read `DATABASE_URL`.
- Local work still works: point `DATABASE_URL` back to `localhost` to use your own database.
- After the final presentation, change the database password (Supabase: Project Settings → Database).

## Updating the cloud data

After each new crawl, either crawl straight into the cloud (set `DATABASE_URL` to the cloud string before
`python3 run_pipeline.py`), or crawl locally and push the result:

```bash
DATABASE_URL="<cloud string>" python3 -m crawler.load_jsonl crawler/output/pages.jsonl
```

`load_jsonl` adds new pages, updates changed pages and skips the rest, in batches of 500 rows.
