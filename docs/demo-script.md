# Demo Video Script (about 2 minutes)

For the supervisor. Record the screen with the search page open in a browser; one person speaks.
Before recording: open the site once (the free server needs a minute to wake up) and close other tabs.

| Time | Screen | What to say |
| --- | --- | --- |
| 0:00–0:15 | Home page | "This is IRIS, our search engine. It crawled ten websites – about 4,700 pages – and ranks them with TF-IDF and cosine similarity." |
| 0:15–0:40 | Type *inverted index*, press Enter | "Results come back in a few milliseconds of database time. Each result shows its rank, score, site and the query words it contains; the words are in bold in the snippet." |
| 0:40–1:05 | Click *How was this ranked?* on the first result | "This page shows every number behind the score: term frequency, document frequency, IDF, the cosine formula and the title bonus. It gives the same score as our ranking function." |
| 1:05–1:25 | Back; choose *CIU website* in the site menu; search *academic calendar* | "We can limit the search to one site. We also crawled the public pages of our university." |
| 1:25–1:40 | Search *tolga yirtici* (no Turkish letters) | "Turkish letters are folded, so the name is found even when typed without them, and the title bonus puts the person's own page first." |
| 1:40–1:55 | Search *football world cup* | "If a word is not in our collection, IRIS says so instead of showing unrelated pages." |
| 1:55–2:05 | GitHub page: README, green *Tests* check | "All code is on GitHub; 122 automated tests run on every pull request, and the collection is re-crawled every week." |

Check each search on the live site the day before recording, because the collection changes after each re-crawl.
