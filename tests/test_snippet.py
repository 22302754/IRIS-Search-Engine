"""Snippet around the first query word, and highlighting of the query words on the results page."""
from web.app import _snippet, app, highlight


TEXT = " ".join(f"w{i}" for i in range(50)) + " The inverted indexes of a search engine " + \
       " ".join(f"x{i}" for i in range(50))


def test_snippet_starts_near_the_first_query_word():
    snippet = _snippet("", TEXT, "inverted index")
    words = snippet.replace("… ", "").replace(" …", "").split()
    assert len(words) == 30
    assert words.index("inverted") == 10          # the 10 words before it are kept
    assert snippet.startswith("… ") and snippet.endswith(" …")


def test_snippet_matches_word_forms_through_stemming():
    assert "indexes" in _snippet("", TEXT, "index")


def test_snippet_without_query_word_uses_the_description():
    assert _snippet("A short description.", TEXT, "zebra") == "A short description."


def test_snippet_of_short_page_has_no_dots():
    assert _snippet("", "Flask routing guide", "routing") == "Flask routing guide"


def test_highlight_bolds_query_words_and_escapes_html():
    html = str(highlight("Inverted <script>x</script> indexes, explained", "inverted index"))
    assert "<strong>Inverted</strong>" in html
    assert "<strong>indexes,</strong>" in html
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_results_page_shows_bold_query_words(monkeypatch):
    record = {"id": 1, "title": "Inverted index", "url": "https://example.com/ii",
              "snippet": "An inverted index maps terms to pages.", "score": 0.9}
    monkeypatch.setitem(app.config, "SEARCH_PROVIDER", lambda query: [record])
    page = app.test_client().get("/results?q=inverted+index").get_data(as_text=True)
    assert "<strong>inverted</strong>" in page
    assert "<strong>index</strong>" in page
