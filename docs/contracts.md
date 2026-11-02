# IRIS – Module Contracts

These are the agreed connections between the modules. Each module may change its inside freely,
but **these names, columns and formats change only by team decision** (write it in `docs/meeting-notes.md`).

```
crawler ──► pages table ──► indexer ──► terms + postings ──► ranker ──► /search API ──► web page
                 ▲               │                              ▲
                 └── preprocess() is used by BOTH ──────────────┘
```

| # | Between | Contract | Status |
| --- | --- | --- | --- |
| 1 | Crawler → Indexer | `pages` table (below) | Done – `crawler/pages_table.sql` |
| 2 | Pre-processing → Indexer and Ranker | `preprocess(text) -> list[str]` | Done |
| 3 | Indexer → Ranker | `terms` and `postings` tables (below) | Done |
| 4 | Ranker → API | `rank(query, k=10) -> list[tuple[int, float]]` | Done |
| 5 | API → Interface | `GET /search?q=...&page=1` JSON (below) | Done |

## 1. `pages` table (filled by the crawler)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | SERIAL PRIMARY KEY | used as `page_id` everywhere |
| `url` | TEXT UNIQUE NOT NULL | canonical URL |
| `site` | VARCHAR(50) | `books`, `quotes`, `python-docs`, `mdn`, `ir-book`, `wikipedia`, `postgresql-docs`, `scrapy-docs`, `flask-docs`, `ciu` |
| `title` | TEXT | shown in results |
| `description` | TEXT | meta description, may be empty |
| `language` | VARCHAR(10) | `en` (site default when the page does not say) |
| `text` | TEXT NOT NULL | clean main text; paragraphs separated by `\n` |
| `word_count` | INTEGER | |
| `content_hash` | CHAR(40) | SHA-1 of the text, used for duplicates and change detection |
| `etag` | TEXT | from the web server, used to ask "has it changed?" |
| `last_modified` | TEXT | from the web server, same purpose |
| `crawled_at` | TIMESTAMPTZ | first time the page was saved |
| `updated_at` | TIMESTAMPTZ | last time the page's text changed; **the indexer re-indexes pages with `updated_at` newer than its last run** |

Get the data without crawling: `python3 -m crawler.load_jsonl crawler/output/pages.jsonl`

## 2. `preprocess(text)`

```python
from preprocessing.preprocess import preprocess

preprocess("The Crawlers are RUNNING fast!")   # -> ["crawler", "run", "fast"]
```

- File: `preprocessing/preprocess.py` (with an empty `preprocessing/__init__.py`).
- Steps in this order: lowercase → tokenise → drop punctuation and numbers → drop stop words → Porter stemming (NLTK).
- Returns a list (duplicates kept, so the indexer can count term frequency). Empty text → `[]`.
- The indexer and the query side **must import this same function**; never copy it.

## 3. `terms` and `postings` tables (filled by the indexer)

```sql
CREATE TABLE terms (
    id        SERIAL PRIMARY KEY,
    term      TEXT    NOT NULL UNIQUE,
    doc_freq  INTEGER NOT NULL          -- number of pages that contain the term
);

CREATE TABLE postings (
    term_id   INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
    page_id   INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    tf        INTEGER NOT NULL,         -- times the term appears in the page
    PRIMARY KEY (term_id, page_id)
);

CREATE TABLE page_norms (
    page_id   INTEGER PRIMARY KEY REFERENCES pages(id) ON DELETE CASCADE,
    norm      DOUBLE PRECISION NOT NULL -- length of the page's TF-IDF vector, for cosine
);
```

Proposal – SE #1 confirms the final version in `docs/schema.sql`.

## 4. `rank(query, k=10)`

```python
from ranker.rank import rank

rank("inverted index compression", k=10)
# -> [(812, 0.4137), (77, 0.3921), ...]   (page_id, cosine score), best first
```

- Calls `preprocess(query)`; words not in `terms` are ignored.
- Empty or stop-words-only query → `[]`.
- Weight = tf × log(N / df), N = number of pages; score = cosine similarity.

## 5. `GET /search?q=...&page=1`

```json
{
  "query": "inverted index",
  "total": 42,
  "page": 1,
  "per_page": 10,
  "time_ms": 85,
  "results": [
    {
      "id": 812,
      "title": "Inverted index",
      "url": "https://en.wikipedia.org/wiki/Inverted_index",
      "snippet": "An inverted index is a database index storing a mapping from content ...",
      "score": 0.4137
    }
  ]
}
```

No results → `"total": 0, "results": []`. Missing or empty `q` → HTTP 400 with `{"error": "empty query"}`.

Additions in week 5 (the fields above are unchanged):

- Optional `site=<name>` (a `pages.site` value) limits the results to one site; an unknown name is ignored.
  The answer then also has `"site": "<name>"`.
- Only pages that contain **every** query word (after `preprocess()`) are returned. A query word that is not
  in the index means the collection has nothing on it, so the answer is `"total": 0`.
  `rank()` itself is unchanged; the filter is `ranker/explain.py → keep_matching_pages()`.
- Each result also has `"site"` and `"matched_terms"` (`{"invert": 2, "index": 2}`: the query terms in the page
  and how often each occurs).
- `GET /explain?q=...&id=<page id>` shows every number behind one result's score (HTML page).
