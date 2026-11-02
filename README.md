# IRIS – Intelligent Information Retrieval System

**Intelligent Information Retrieval System with Web Crawling and Ranking Algorithms** – a small but complete
search engine built as our ENGI 401/402 capstone project at Cyprus International University, Faculty of Engineering.
It crawls ten websites, cleans and indexes their text, and ranks results with TF-IDF and cosine similarity.

Supervisor: **Asst. Prof. Dr. Tolga Yırtıcı** · Term: 2026/2027 Fall

## Team

| Member | Department | Role | Modules |
| --- | --- | --- | --- |
| Mohammed Nouri | Computer Engineering | Team leader · Crawler & Infrastructure | `crawler/`, `infra/`, `run_pipeline.py`, database, GitHub Actions |
| Yazen Alhuri | Artificial Intelligence Engineering | AI Engineer · Pre-processing & Ranking | `preprocessing/`, `ranker/` |
| Hani Abu Kwaik | Software Engineering | Software Engineer #1 · Indexer & API | `indexer/`, `/search` API |
| Elpi Kipoyi Ndonganani | Software Engineering | Software Engineer #2 · Interface, Testing & Scrum | `web/` page, tests, meeting notes |

## How it works

```mermaid
flowchart LR
    W[10 websites] -->|Scrapy, robots.txt, 1 req/s| C[crawler]
    C --> P[(pages)]
    P --> I[indexer]
    I --> T[(terms · postings · page_norms)]
    T --> R[ranker<br/>TF-IDF + cosine]
    R --> A[/search API/]
    A --> UI[search page]
    PP[preprocess] -.-> I
    PP -.-> R
```

The names, table columns and JSON format that connect the modules are fixed in
**[docs/contracts.md](docs/contracts.md)**.

## Status

The search engine works end to end: a query on the search page is answered from the shared database with pages
ranked by TF-IDF and cosine similarity.

| Module | Owner | Status |
| --- | --- | --- |
| Crawler – 10 sites (CIU added in week 5), cleaning, duplicates, incremental re-crawl | Mohammed | ✅ **4,697 pages, 7.66 million words** ([crawl report](docs/crawl-report.md)) |
| Shared database (Supabase PostgreSQL, Frankfurt) | Mohammed | ✅ |
| Operations – backups, data-quality check, smoke test, weekly crawl on GitHub Actions | Mohammed | ✅ ([deployment](docs/deployment.md)) |
| `preprocess(text)` – tokens, stop words, Porter stemming | Yazen | ✅ |
| `rank(query, k)` – TF-IDF + cosine, hand-calculated tests, 20 test queries | Yazen | ✅ ([test queries](docs/test-queries.md)) |
| Indexer `python3 -m indexer.build` – full and incremental | Hani | ✅ 102,128 terms, 1.46 million postings ([schema](docs/schema.sql)) |
| `GET /search` JSON API – all 20 benchmark queries under 1 s | Hani | ✅ |
| Search page and results page – paging, snippets with the query words in bold | Elpi | ✅ |
| Site filter, all-words matching, ranking details per result and `/explain` page | Team | ✅ |
| Tests on every pull request (GitHub Actions) | Elpi | ✅ 122 tests ([testing](docs/report/testing-section.md)) |
| Public website (Render) | Mohammed | 🔄 Next step |

## Roadmap

| Week | Dates | Goal | State |
| --- | --- | --- | --- |
| 1 | 5–11 Oct | Repository, roles, seed sites, robots.txt check, test spider | ✅ |
| 2 | 12–18 Oct | Full crawler and storage (1,360 pages); module contracts; search page | ✅ |
| 3 | 19–25 Oct | Incremental re-crawl, 9 sites (3,769 pages), shared cloud database | ✅ |
| 4 | 26 Oct – 1 Nov | **Milestone: first end-to-end search** – pre-processing, index, ranking, API, tests, weekly crawl | ✅ (public website pending) |
| 5 | 2–8 Nov | Better ranking (title boost) and interface; public website | ⏳ Current week |
| 6 | 9–15 Nov | Evaluation of the 20 test queries (precision of the top 10 results) | ⏳ |
| 7 | 16–22 Nov | Testing, fixes, final demo preparation | ⏳ |
| 8 | 23–29 Nov | Final report and presentation | ⏳ |

## Repository structure

```
IRIS-Search-Engine/
├── crawler/            web crawler (Scrapy): rules per site, cleaning, duplicates, storage, crawl report
├── preprocessing/      preprocess(text): tokens, stop words, stemming
├── indexer/            inverted index builder (terms, postings, page_norms), full or incremental
├── ranker/             rank(query, k): TF-IDF + cosine similarity; check of the 20 test queries
├── web/                Flask app: search page, results page, /search JSON API
├── infra/              backup, restore, data-quality check, smoke test
├── tests/              122 pytest tests for every module
├── docs/               requirements, contracts, schema, test queries, meeting notes
│   ├── report/         draft sections of the final report
│   └── weekly/         weekly submission notes
├── .github/workflows/  tests on every pull request · weekly crawl
├── run_pipeline.py     robots check → crawl → report → index, in one command
├── render.yaml         hosting settings for Render
└── requirements.txt
```

## Getting started

```bash
git clone https://github.com/22302754/IRIS-Search-Engine.git
cd IRIS-Search-Engine
python3 -m pip install -r requirements.txt
python3 -m pytest
```

Put the shared database connection (sent to you privately by Mohammed) in a `.env` file in the repository root.
Never commit it and never post it in the group.

```
DATABASE_URL=postgresql://...
```

## Commands

| Command | What it does |
| --- | --- |
| `python3 -m flask --app web.app run --port 8000` | Run the search engine at `http://localhost:8000` |
| `python3 run_pipeline.py` | robots.txt check → crawl → crawl report → index (`--only ir-book` for one site) |
| `python3 -m indexer.build` | Update the index for new or changed pages (`--full` rebuilds everything) |
| `python3 -m ranker.check_queries` | Check that each of the 20 test queries has a relevant page |
| `python3 -m ranker.judging_sheet` | Top 10 of each test query → `docs/judging-sheet.csv` for Precision@10 (`--score` to compute it) |
| `python3 -m infra.backup_db` | Back up the database to `backups/<date>/` |
| `python3 -m infra.restore_db backups/<date>` | Restore a backup (safe by default) |
| `python3 -m infra.check_quality` | Data-quality report → `docs/data-quality.md` |
| `python3 -m infra.smoke_test --base-url <url>` | Time the 20 test queries against a running site |
| `python3 -m pytest` | Run all tests |

## Documents

| Area | Document | What it is |
| --- | --- | --- |
| Project | [requirement.md](docs/requirement.md) | Functional and non-functional requirements |
| | [contracts.md](docs/contracts.md) | How the modules connect: tables, functions, JSON |
| | [meeting-notes.md](docs/meeting-notes.md) | Decisions log and meeting notes |
| Data | [seed-sites.md](docs/seed-sites.md) | The crawled sites and their robots.txt check |
| | [crawl-report.md](docs/crawl-report.md) | Pages and words per site from the latest crawl |
| | [data-quality.md](docs/data-quality.md) | Leftover menu text, short pages, near-duplicates |
| | [crawler/README.md](crawler/README.md) | How to run the crawler |
| Database | [schema.sql](docs/schema.sql) | All tables: pages, terms, postings, page_norms, index_state |
| | [cloud-database.md](docs/cloud-database.md) | The shared Supabase database |
| | [search-index.md](docs/search-index.md) | Building and updating the search index |
| Operations | [deployment.md](docs/deployment.md) | Hosting, weekly crawl, backups, checks |
| Evaluation | [test-queries.md](docs/test-queries.md) | The 20 test queries and how relevance is judged |
| Report | [report/](docs/report/) | Crawler, infrastructure, indexing, ranking, testing and interface sections |
| | [demo-script.md](docs/demo-script.md) | The 2-minute demo video, step by step |
| Weekly | [weekly/](docs/weekly/) | Weekly submission notes |

## How we work

1. Every task is a GitHub issue, assigned to one person, in a weekly milestone.
2. Work on a branch (`git checkout -b indexer-build`), never directly on `main` (it is protected).
3. Open a pull request and ask one teammate to review; GitHub Actions runs all tests on it.
4. Merge when the review is done and the tests are green; then delete the branch.
5. Never commit `.env`, passwords or the database connection.
