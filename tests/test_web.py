from web.app import app


def get_page(url):
    client = app.test_client()
    response = client.get(url)
    return response.status_code, response.get_data(as_text=True)


def test_search_page_loads():
    status, html = get_page("/")
    assert status == 200
    assert "IRIS" in html


def test_results_show_for_a_query():
    status, html = get_page("/results?q=crawler")
    assert status == 200
    assert "25 results" in html
    assert "Fake result 1" in html


def test_first_page_has_ten_results():
    _, html = get_page("/results?q=crawler")
    assert html.count('class="result"') == 10
    assert "Page 1 of 3" in html


def test_second_page_works():
    _, html = get_page("/results?q=crawler&page=2")
    assert "Page 2 of 3" in html
    assert "Fake result 11" in html


def test_last_page_has_five_results():
    _, html = get_page("/results?q=crawler&page=3")
    assert html.count('class="result"') == 5


def test_no_results_state():
    _, html = get_page("/results?q=nothing")
    assert "No results found" in html


def test_empty_query_shows_no_results():
    _, html = get_page("/results?q=")
    assert "No results found" in html