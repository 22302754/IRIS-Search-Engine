# Building the IRIS search index

The web search reads page content from the PostgreSQL `pages` table and ranks it
using the TF-IDF index in `terms`, `postings`, and `page_norms`.

## Build or update the index

Ensure the repository-root `.env` file contains a valid `DATABASE_URL`, then run:

```bash
python -m indexer.build
```

The first run preprocesses every page and creates the index tables in a single
database transaction. Searches continue to see the previous complete index
until that build commits.

Later runs are incremental: the indexer reads only pages whose
`COALESCE(updated_at, crawled_at)` timestamp is newer than its last successful
checkpoint, replaces their postings, removes references for deleted pages, and
refreshes the global document frequencies and vector norms. It does not tokenize
or rewrite postings for unchanged pages. Running the command again when no pages
changed is safe and avoids a full rebuild. To intentionally rebuild every table,
use:

```bash
python -m indexer.build --full
```

The index uses the shared `preprocessing.preprocess` function for both documents
and queries. It lowercases and tokenizes English text, removes stop words, and
applies the NLTK Porter stemmer.

## Verify the application

Run the test suite:

```bash
python -m pytest
```

Start the Flask application:

```bash
python -m flask --app web.app run
```

Open the displayed local URL and submit a search. The JSON endpoint is available
at `/search?q=your+query`.

Never commit or share the `.env` file: it contains database credentials.
