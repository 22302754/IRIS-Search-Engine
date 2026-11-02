"""More tests for preprocess() in preprocessing/preprocess.py (the first 3 are in test_search_modules.py).

These tests describe what the function does TODAY. The index was built with it, so a change here
means rebuilding the index (python3 -m indexer.build --full); a failing test is the reminder.
"""
from preprocessing.preprocess import preprocess


def test_mixed_case_gives_the_same_terms():
    assert preprocess("Python PYTHON python pYtHoN") == ["python"] * 4
    assert preprocess("Inverted INDEX") == preprocess("inverted index")


def test_numbers_are_removed_and_split_words():
    assert preprocess("Error 404 in 2026") == ["error"]
    assert preprocess("3.14 1,000 42") == []
    assert preprocess("python3 html5") == ["python", "html"]      # digits are cut out of words


def test_porter_stemming_merges_word_forms():
    assert preprocess("connect connected connecting connection connections") == ["connect"] * 5
    assert preprocess("indexing indexes indexed") == ["index"] * 3
    assert preprocess("ranking ranked ranks") == ["rank"] * 3


def test_url_is_split_into_its_words():
    assert preprocess("https://www.python.org/3/tutorial/classes.html") == [
        "http", "www", "python", "org", "tutori", "class", "html"]


def test_very_short_words():
    assert preprocess("a I") == []                       # one-letter stop words are removed
    assert preprocess("x y db") == ["x", "y", "db"]      # other short words are kept


def test_punctuation_splits_words():
    assert preprocess("database-index, (search); engine!") == ["databas", "index", "search", "engin"]
    assert preprocess("os.path.join()") == ["os", "path", "join"]


def test_duplicates_and_order_are_kept_for_term_frequency():
    assert preprocess("web crawler web") == ["web", "crawler", "web"]


def test_none_and_whitespace_give_empty_list():
    assert preprocess(None) == []
    assert preprocess("   \n\t ") == []


def test_query_and_page_produce_matching_terms():
    page_terms = set(preprocess("The crawler downloads pages and follows their links."))
    assert set(preprocess("crawler page links")) <= page_terms


def test_turkish_and_accented_letters_are_folded_to_plain_letters():
    # without folding, "Yırtıcı" would be cut into "y", "rt", "c"
    assert preprocess("Tolga Yırtıcı") == ["tolga", "yirtici"]
    assert preprocess("Tolga YIRTICI") == ["tolga", "yirtici"]
    assert preprocess("İstanbul çağrı café") == ["istanbul", "cagri", "cafe"]
