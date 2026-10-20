-- IRIS: the pages table filled by the crawler.
-- Software Engineer #1: copy this into docs/schema.sql (the crawler runs it only if the table does not exist).
-- Contract columns: id, url, title, text, crawled_at. The others are extra information from the crawler.
-- Week 3: etag, last_modified and updated_at support incremental re-crawls; the indexer can
-- re-index only pages with updated_at later than its last run.

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
