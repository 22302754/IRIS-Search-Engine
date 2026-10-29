import pytest

from web.app import SearchBackendUnavailable, app


def make_results(count=25):
    return [
        {
            "id": index,
            "title": f"Result {index}",
            "url": f"https://example.com/page-{index}",
            "snippet": f"Snippet for result {index}.",
            "score": round(1 - index * 0.03, 4),
        }
        for index in range(1, count + 1)
    ]


def get_page(url):
    return app.test_client().get(url)


@pytest.fixture
def search_results(monkeypatch):
    records = make_results()
    monkeypatch.setitem(app.config, "SEARCH_PROVIDER", lambda query: records)
    return records


def test_search_page_loads():
    response = get_page("/")
    assert response.status_code == 200
    assert b"IRIS" in response.data


def test_search_api_returns_contract_fields(search_results):
    response = get_page("/search?q=crawler")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["query"] == "crawler"
    assert payload["total"] == 25
    assert payload["page"] == 1
    assert payload["per_page"] == 10
    assert isinstance(payload["time_ms"], int)
    assert payload["results"][0] == search_results[0]


def test_search_api_rejects_empty_query():
    response = get_page("/search?q=")
    assert response.status_code == 400
    assert response.get_json() == {"error": "empty query"}


def test_search_api_returns_empty_result_set(monkeypatch):
    monkeypatch.setitem(app.config, "SEARCH_PROVIDER", lambda query: [])
    response = get_page("/search?q=unmatched")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["total"] == 0
    assert payload["results"] == []


def test_search_api_reports_missing_backend(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    response = get_page("/search?q=crawler")
    assert response.status_code == 503
    assert response.get_json() == {"error": "search backend unavailable"}


def test_results_show_real_result_fields(search_results):
    response = get_page("/results?q=crawler")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "25 results" in html
    assert "ms" in html
    assert "Result 1" in html
    assert "https://example.com/page-1" in html
    assert "Snippet for result 1." in html
    assert "0.9700" in html


def test_first_page_has_ten_results(search_results):
    response = get_page("/results?q=crawler")
    html = response.get_data(as_text=True)
    assert html.count('class="result"') == 10
    assert "Page 1 of 3" in html


def test_second_page_works(search_results):
    response = get_page("/results?q=crawler&page=2")
    html = response.get_data(as_text=True)
    assert "Page 2 of 3" in html
    assert "Result 11" in html


def test_last_page_has_five_results(search_results):
    response = get_page("/results?q=crawler&page=3")
    assert response.get_data(as_text=True).count('class="result"') == 5


def test_no_results_state(monkeypatch):
    monkeypatch.setitem(app.config, "SEARCH_PROVIDER", lambda query: [])
    response = get_page("/results?q=nothing")
    assert "No results found" in response.get_data(as_text=True)


def test_empty_query_shows_no_results():
    response = get_page("/results?q=")
    assert "No results found" in response.get_data(as_text=True)


def test_results_show_backend_unavailable_state(monkeypatch):
    def unavailable_provider(query):
        raise SearchBackendUnavailable("test backend unavailable")

    monkeypatch.setitem(app.config, "SEARCH_PROVIDER", unavailable_provider)
    response = get_page("/results?q=crawler")
    assert response.status_code == 503
    assert b"Search is unavailable" in response.data