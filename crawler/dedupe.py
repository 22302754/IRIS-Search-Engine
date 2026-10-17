"""
IRIS - duplicate control.

Two kinds of duplicates are blocked:
  1. the same URL (after canonicalize(): no #fragment, no tracking params, sorted query)
  2. the same text at a different URL (same content_hash)

Already-saved URLs and hashes are loaded from the database / JSON Lines file at start,
so running the crawler again only adds new pages.
"""
from crawler.cleaner import canonicalize


class Deduplicator:
    def __init__(self):
        self.urls = set()
        self.hashes = set()

    def load(self, urls=(), hashes=()):
        """Register pages that were saved in an earlier run."""
        self.urls.update(canonicalize(u) for u in urls if u)
        self.hashes.update(h for h in hashes if h)

    def is_new_url(self, url):
        """True the first time a URL is seen; False for every repeat. Registers the URL."""
        key = canonicalize(url)
        if key in self.urls:
            return False
        self.urls.add(key)
        return True

    def is_new_content(self, content_hash):
        """True the first time a text fingerprint is seen; False for copies. Registers the hash."""
        if not content_hash or content_hash in self.hashes:
            return False
        self.hashes.add(content_hash)
        return True

    def __len__(self):
        return len(self.urls)
