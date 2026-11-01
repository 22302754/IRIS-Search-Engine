-- IRIS search-engine schema.
-- The crawler creates and maintains pages; the indexer maintains all other tables.

CREATE TABLE IF NOT EXISTS pages (
    id            SERIAL PRIMARY KEY,
    url           TEXT        NOT NULL UNIQUE,
    site          VARCHAR(50),
    title         TEXT,
    description   TEXT,
    language      VARCHAR(10),
    text          TEXT        NOT NULL,
    word_count    INTEGER,
    content_hash  CHAR(40),
    etag          TEXT,
    last_modified TEXT,
    crawled_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS pages_site_idx         ON pages (site);
CREATE INDEX IF NOT EXISTS pages_content_hash_idx ON pages (content_hash);
CREATE INDEX IF NOT EXISTS pages_updated_at_idx   ON pages (updated_at);

CREATE TABLE IF NOT EXISTS terms (
    id       SERIAL PRIMARY KEY,
    term     TEXT    NOT NULL UNIQUE,
    doc_freq INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS postings (
    term_id INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
    page_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    tf      INTEGER NOT NULL,
    PRIMARY KEY (term_id, page_id)
);

CREATE INDEX IF NOT EXISTS postings_term_id_idx ON postings (term_id);
CREATE INDEX IF NOT EXISTS postings_page_id_idx ON postings (page_id);

CREATE TABLE IF NOT EXISTS page_norms (
    page_id INTEGER PRIMARY KEY REFERENCES pages(id) ON DELETE CASCADE,
    norm    DOUBLE PRECISION NOT NULL
);

-- A single checkpoint lets the indexer process only changed pages on later runs.
CREATE TABLE IF NOT EXISTS index_state (
    singleton       BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    last_indexed_at TIMESTAMPTZ NOT NULL
);
