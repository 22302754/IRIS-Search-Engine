import math

from indexer.build import _prepare_index
from preprocessing.preprocess import preprocess


def test_preprocess_contract_example():
    assert preprocess("The Crawlers are RUNNING fast!") == ["crawler", "run", "fast"]


def test_preprocess_removes_stop_words_punctuation_and_numbers():
    assert preprocess("A 123, database-index!") == ["databas", "index"]


def test_preprocess_returns_empty_for_empty_or_stop_word_text():
    assert preprocess("") == []
    assert preprocess("the and are") == []


def test_prepare_index_calculates_term_frequencies_and_document_frequencies():
    term_frequencies, document_frequencies, norms = _prepare_index(
        [(1, "red red blue"), (2, "blue green"), (3, "")]
    )

    assert term_frequencies[1] == {"red": 2, "blue": 1}
    assert term_frequencies[2] == {"blue": 1, "green": 1}
    assert term_frequencies[3] == {}
    assert document_frequencies == {"red": 1, "blue": 2, "green": 1}
    assert norms[1] == math.sqrt((2 * math.log(3)) ** 2 + math.log(1.5) ** 2)
    assert norms[2] == math.sqrt(math.log(1.5) ** 2 + math.log(3) ** 2)
    assert norms[3] == 0


def test_prepare_index_handles_no_documents():
    term_frequencies, document_frequencies, norms = _prepare_index([])

    assert term_frequencies == {}
    assert document_frequencies == {}
    assert norms == {}
