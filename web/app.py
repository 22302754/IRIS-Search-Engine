import math
from flask import Flask, render_template, request

app = Flask(__name__)

PER_PAGE = 10

# 25 fake results so we can test paging
FAKE_RESULTS = [
    {
        "title": f"Fake result {i}",
        "url": f"https://example.com/page-{i}",
        "snippet": "This is a placeholder snippet for testing the results page.",
        "score": round(1 - i * 0.03, 4),
    }
    for i in range(1, 26)
]


@app.route("/")
def home():
    return render_template("search.html")


@app.route("/results")
def results():
    query = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)

    # Fake rule: an empty search, or the word "nothing", shows the "no results" state
    if not query or query.lower() == "nothing":
        found = []
    else:
        found = FAKE_RESULTS

    total = len(found)
    total_pages = max(1, math.ceil(total / PER_PAGE))
    page = min(max(page, 1), total_pages)
    start = (page - 1) * PER_PAGE

    return render_template(
        "results.html",
        query=query,
        results=found[start:start + PER_PAGE],
        total=total,
        page=page,
        total_pages=total_pages,
    )


if __name__ == "__main__":
    app.run(debug=True)