# User Interface — Report Section

Owner: Software Engineer #2 (Interface, Testing & Scrum) · Code: `web/app.py`, `web/templates/`, `web/static/style.css`

## Goals

The interface has one job: let a person type a few words and find the right page quickly. It follows the
requirements: a clean landing page with one search box (FR-5.1), results with title, linked address and snippet
(FR-5.3), paging and a clear "no results" state (FR-5.4), and an answer in under one second (NFR-1). The design uses one serif typeface for headings, a sans-serif
for text, a light paper background and one accent colour, so the results are easy to scan.

## Pages

| Page | Address | What it shows |
| --- | --- | --- |
| Home | `/` | The IRIS logo, one search box, a site menu (*All sites* or one of the 10 sites) and a *Search* button |
| Results | `/results?q=…&site=…&page=…` | Number of results and search time, 10 results per page, paging, the search box with the query |
| Ranking details | `/explain?q=…&id=…` | Every number behind one result's score (see the ranking section) |
| JSON API | `/search?q=…` | The same results for programs (module contract) |

**Searching.** Pressing *Enter* or the *Search* button starts the search; a small script makes *Enter* work even
when the site menu has the focus. An empty query is not sent. The chosen site stays selected on the results
page and in the paging links.

**Each result** shows its rank number, the title (linked to the page), the address, a snippet, the score, the site
as a coloured label, the query words found in the page with their counts (for example `index ×2`), and the
link *How was this ranked?*.

**Snippets.** The snippet is about 30 words of the page around the first query word, not simply the start of
the page, with `…` where text was cut. The query words are shown in **bold** in the title and the snippet. Word
forms are matched through stemming, so a search for *index* also highlights *indexes*. All page text is
HTML-escaped before the bold tags are added, so text from a crawled page can never run as code in the browser.

**No results.** When no page contains all the query words, the page says *No results found* and explains that
IRIS searches only the pages it has crawled, instead of showing loosely related pages.

**Errors.** If the database cannot be reached, the results page shows *Search is unavailable* with HTTP status
503 and the JSON API returns `{"error": "search backend unavailable"}`; an empty query to the API returns HTTP 400.

## Screenshots

*[Add: the home page, a results page for "inverted index", the ranking-details page, and the "No results found"
page.]*

## Testing

The interface is covered by `tests/test_web.py` (pages, paging, empty and very long queries, special characters,
error states), `tests/test_snippet.py` (snippet window, stemming, bold words, HTML escaping),
`tests/test_search_filters.py` (site menu, ranking details) and `tests/test_end_to_end.py` (a real search through
the indexer, the ranker and the web app). The manual browser checks are listed in the testing section.
