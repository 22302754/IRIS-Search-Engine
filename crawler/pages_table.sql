-- IRIS: the pages table filled by the crawler.
-- Software Engineer #1: copy this into docs/schema.sql (the crawler also runs it, it does nothing if the table exists).
-- Contract columns: id, url, title, text, crawled_at. The others are extra information from the crawler.

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
    crawled_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS pages_site_idx         ON pages (site);
CREATE INDEX IF NOT EXISTS pages_content_hash_idx ON pages (content_hash);
