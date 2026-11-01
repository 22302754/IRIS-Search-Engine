"""Unit tests for the data-quality checks (infra/check_quality.py)."""
from infra.check_quality import (build_report, duplicate_titles, near_duplicates, simhash, size_outliers,
                                 template_lines, unknown_language)

BODY = " ".join(f"term{i}" for i in range(200))   # 200 different words, like a real page


def page(url, site="s", text=BODY, title="T", language="en"):
    return {"url": url, "site": site, "title": title, "language": language,
            "text": text, "word_count": len(text.split())}


def test_unknown_language_and_sizes():
    pages = [page("a"), page("b", language="unknown"), page("c", text="tiny page"), page("d", text="w " * 25000)]
    assert [p["url"] for p in unknown_language(pages)] == ["b"]
    short, long = size_outliers(pages)
    assert [p["url"] for p in short] == ["c"] and [p["url"] for p in long] == ["d"]


def test_template_line_found_only_when_repeated_on_many_pages():
    footer = "Copyright 2026 Example Documentation Team"
    pages = [page(f"u{i}", text=f"unique words number {i} " * 20 + "\n" + (footer if i < 12 else "other")) for i in range(30)]
    found = template_lines(pages)
    assert len(found) == 1 and found[0][1] == footer and found[0][2] == 12
    assert template_lines(pages[:10]) == []          # too few pages in the site to judge


def test_duplicate_titles_are_grouped_per_site():
    pages = [page("a", title="Index"), page("b", title="Index"), page("c", site="other", title="Index")]
    assert duplicate_titles(pages) == [("s", "Index", ["a", "b"])]


def test_simhash_close_for_small_edits_far_for_different_text():
    edited = BODY + " plus one extra sentence at the end"
    other = " ".join(f"other{i}" for i in range(200))
    assert bin(simhash(BODY) ^ simhash(edited)).count("1") <= 6
    assert bin(simhash(BODY) ^ simhash(other)).count("1") > 10


def test_near_duplicates_pairs():
    pages = [page("a"), page("b", text=BODY), page("c", text="completely different words about css flexbox " * 8)]
    pairs = near_duplicates(pages)
    assert [(a, b) for a, b, _ in pairs] == [("a", "b")]


def test_report_has_summary_and_recrawl_list():
    report, recrawl = build_report([page("a"), page("b", language="unknown")], "test")
    assert "| Language unknown | 1 |" in report
    assert [p["url"] for p in recrawl] == ["b"]
