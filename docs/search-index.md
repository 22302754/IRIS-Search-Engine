# Building the IRIS search index

The web search reads page content from the PostgreSQL `pages` table and ranks it
using the TF-IDF index in `terms`, `postings`, and `page_norms`.

## Build or rebuild the index

Ensure the repository-root `.env` file contains a valid `DATABASE_URL`, then run:

```bash
python -m indexer.build
```

The indexer preprocesses every page and replaces the index tables in a single
database transaction. Searches continue to see the previous complete index
until the rebuild commits. Running the command again is safe.

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
