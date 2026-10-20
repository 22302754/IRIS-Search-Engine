# IRIS – Intelligent Information Retrieval System

A small but complete search engine built as our ENGI 401 capstone at Cyprus International University.
It crawls nine websites, indexes their text, and ranks results with TF-IDF and cosine similarity.

Supervisor: Asst. Prof. Dr. Tolga Yırtıcı · Team: Elpi Kipoyi Ndonganani, Mohammed Nouri, Hani Abu Kwaik, Yazen Alhuri

## Pipeline

```
Crawler → pages table → Indexer (uses preprocess) → terms + postings → Ranker (uses preprocess) → /search API → Web page
```

How the modules connect (table columns, function names, JSON format): **[docs/contracts.md](docs/contracts.md)**.

## Modules and status

| Folder | Module | Owner | Status |
| --- | --- | --- | --- |
| `crawler/` | Crawler, robots.txt check, storage, incremental re-crawl, crawl report | Computer Engineer | Done – 9 sites, up to 4,310 pages ([report](docs/crawl-report.md)) |
| `preprocessing/` | `preprocess(text)` | AI Engineer | Not in `main` yet |
| `indexer/` | Inverted index builder | Software Engineer #1 | Not in `main` yet |
| `ranker/` | TF-IDF + cosine, `rank(query, k)` | AI Engineer | Not in `main` yet |
| `web/` | Flask API and search page | Software Engineer #1 / #2 | Not in `main` yet |
| `tests/` | Unit and end-to-end tests | Everyone (CI: Software Engineer #2) | Crawler tests only |
| `docs/` | Requirements, contracts, reports, meeting notes | Everyone | Ongoing |

## Setup

```bash
git clone https://github.com/22302754/IRIS-Search-Engine.git
cd IRIS-Search-Engine
python3 -m pip install -r requirements.txt
python3 -m pytest
```

Database: install PostgreSQL, create a database `iris`, and put the connection in a `.env` file in the
repository root (never commit it):

```
DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/iris
```

Run the whole data pipeline (robots check → crawl → report → index) with one command:

```bash
python3 run_pipeline.py
```

Or load the shared crawl without crawling (ask Mohammed for `pages.jsonl`):

```bash
python3 -m crawler.load_jsonl crawler/output/pages.jsonl
```

## Documents

| Document | What it is |
| --- | --- |
| [docs/requirement.md](docs/requirement.md) | Functional and non-functional requirements |
| [docs/contracts.md](docs/contracts.md) | Connections between modules |
| [docs/seed-sites.md](docs/seed-sites.md) | The crawled sites and the robots.txt check |
| [docs/crawl-report.md](docs/crawl-report.md) | Numbers from the latest crawl |
| [docs/cloud-database.md](docs/cloud-database.md) | The shared cloud PostgreSQL database |
| [docs/report/](docs/report/) | Draft sections of the final report |
| [docs/meeting-notes.md](docs/meeting-notes.md) | Decisions from team meetings |
| [crawler/README.md](crawler/README.md) | How to run the crawler |

## How we work

- Never push to `main`; create a branch, push it, open a pull request.
- Every pull request is reviewed by one teammate before merging.
- Every task is a GitHub issue on the project board: To do → In progress → Review → Done.
