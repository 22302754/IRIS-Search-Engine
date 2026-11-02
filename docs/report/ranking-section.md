# Ranking — Report Section

Author: Yazen (AI Engineer, Pre-processing & Ranking) · Code: `ranker/rank.py` · Tests: `tests/test_rank.py`

## Purpose of the Ranker

The ranker decides the order in which pages are shown. A query such as *inverted index* matches hundreds of the
3,769 pages in the collection, and a user reads only the first few, so the quality of the system depends on
putting the most relevant pages first. IRIS uses the vector space model with TF-IDF weights and cosine
similarity (Salton & Buckley, 1988; Manning et al., 2008, ch. 6). It is simple, needs no training data, and
every score can be checked by hand.

## TF-IDF Weights

Each page and each query is represented as a vector with one dimension per term. The weight of term *t* in
page *d* is

$$w_{t,d} = \mathrm{tf}_{t,d} \times \ln\frac{N}{\mathrm{df}_t}$$

where

- $\mathrm{tf}_{t,d}$ is the number of times *t* occurs in *d* after pre-processing (stored in `postings.tf`);
- $\mathrm{df}_t$ is the number of pages that contain *t* (stored in `terms.doc_freq`);
- $N$ is the number of pages in the collection (`SELECT COUNT(*) FROM pages`).

The first factor rewards pages that use a query word often. The second factor, the inverse document
frequency (IDF), rewards rare words: a word found on every page has $\ln(N/N) = 0$ and does not affect the
ranking, while a word found on one page out of 3,769 has $\ln 3769 \approx 8.2$. The query is weighted the same
way, with $\mathrm{tf}_{t,q}$ = the number of times *t* occurs in the query.

## Cosine Similarity

The score of page *d* for query *q* is the cosine of the angle between their two vectors:

$$\mathrm{score}(q,d) = \cos(\vec q,\vec d) = \frac{\sum_{t \in q} w_{t,q}\, w_{t,d}}{\lVert \vec q \rVert \; \lVert \vec d \rVert}, \qquad \lVert \vec d \rVert = \sqrt{\sum_{t \in d} w_{t,d}^{2}}$$

Dividing by the vector lengths removes the advantage of long pages: a long page contains more words, but its
vector is also longer. Scores lie between 0 and 1, and a page that has exactly the same weighted terms as the
query scores 1.

Because the score is a ratio, the base of the logarithm does not matter: changing it multiplies every weight by
the same constant, which cancels between the numerator and the denominator. IRIS uses the natural logarithm.

## Implementation

`rank(query, k=10)` returns a list of `(page_id, score)` pairs, best first, as agreed in the module contract.

1. The query is passed through the same `preprocess()` function that the indexer used, so query terms match
   index terms. An empty query, or one made only of stop words, punctuation or numbers, returns `[]` without
   touching the database.
2. The query terms are looked up in `terms`. Words that are not in the collection are ignored; if none is
   found, the result is `[]`.
3. For the remaining terms the ranker computes the IDF values and the query vector length $\lVert \vec q \rVert$ in
   Python.
4. One SQL query joins the query terms with `postings`, sums $\mathrm{tf}_{t,d} \cdot \mathrm{idf}_t^2 \cdot \mathrm{tf}_{t,q}$ per
   page (this equals $\sum w_{t,q} w_{t,d}$), divides by the stored page length from `page_norms` and by
   $\lVert \vec q \rVert$, and returns the top *k* pages ordered by score and then by `page_id`, so ties always come
   out in the same order.

The page lengths $\lVert \vec d \rVert$ are computed once by the indexer and stored in `page_norms`, so a search only
reads the postings of the query terms: it never touches pages that share no word with the query.

## Worked Example

Three small pages, already pre-processed:

| Page | Text | Term frequencies |
| --- | --- | --- |
| 1 | web crawler web | web 2, crawler 1 |
| 2 | web index | web 1, index 1 |
| 3 | index rank rank | index 1, rank 2 |

With $N = 3$: *web* and *index* each occur in 2 pages, so their IDF is $a = \ln(3/2) = 0.405465$. *crawler* and
*rank* each occur in 1 page, so their IDF is $b = \ln 3 = 1.098612$.

Page lengths:

| Page | Weights | Length |
| --- | --- | ---: |
| 1 | web $2a$, crawler $b$ | $\sqrt{(2a)^2 + b^2} = 1.365488$ |
| 2 | web $a$, index $a$ | $\sqrt{a^2 + a^2} = 0.573414$ |
| 3 | index $a$, rank $2b$ | $\sqrt{a^2 + (2b)^2} = 2.234323$ |

**Query "web crawler".** The query vector is (web $a$, crawler $b$), with length $\sqrt{a^2 + b^2} = 1.171047$.

| Page | Dot product | Score |
| --- | --- | ---: |
| 1 | $2a \cdot a + b \cdot b = 1.535753$ | $1.535753 / (1.365488 \times 1.171047) = \mathbf{0.960416}$ |
| 2 | $a \cdot a = 0.164402$ | $0.164402 / (0.573414 \times 1.171047) = 0.244830$ |
| 3 | no common term | not returned |

**Query "ranking index".** Pre-processing turns *ranking* into *rank*. The query vector is (rank $b$, index $a$),
with length 1.171047.

| Page | Dot product | Score |
| --- | --- | ---: |
| 3 | $2b \cdot b + a \cdot a = 2.578300$ | $2.578300 / (2.234323 \times 1.171047) = \mathbf{0.985402}$ |
| 2 | $a \cdot a = 0.164402$ | 0.244830 |
| 1 | no common term | not returned |

Page 1 wins the first query because it contains the rare word *crawler*, and its repeated *web* adds to the
score. Page 2 shares only the common word *web*, so it scores low. The same values are checked in
`tests/test_rank.py`, both against an in-memory copy of the tables and against PostgreSQL itself.

## From Ranking to the Search Page

`rank()` scores every page that shares at least one word with the query. The search page applies three further
rules on top of these scores (`ranker/explain.py`, `ranker/search.py`):

1. **Every query word must be in the page.** A page is shown only if it contains all query terms after
   pre-processing. A query word that is not in the index at all means the collection has nothing on the topic,
   so the page answers *No results found* instead of showing pages that match only part of the query.
2. **Title bonus.** A page whose title contains the query words is usually *about* them, while a long page may
   mention them once, for example in its list of references. The final score is

$$\mathrm{score}(q,d) = \cos(\vec q, \vec d) + 0.1 \times \frac{|\text{query terms in the title of } d|}{|\text{query terms}|}$$

   The bonus is at most 0.1, so it reorders pages with similar cosine scores but cannot lift a page with a weak
   text match above a clearly better one. It was added after the query *tolga* ranked a Wikipedia article that
   cites an author named Tolga in its references above the university's staff pages.
3. **Optional site filter**, for example only the CIU website or only the Python documentation.

The page *How was this ranked?* (`/explain`) shows every number behind one result: tf, df, idf and both weights
for each query term, the dot product, both vector lengths, the cosine, the title bonus and the final score. The
values are the same as those of `rank()`, which `tests/test_search_filters.py` checks.

### Accented and Turkish letters

The tokenizer keeps only the letters a–z. Before week 5 a Turkish name such as *Yırtıcı* was therefore cut into
the pieces *y*, *rt* and *c*, and could not be found. `preprocess()` now first folds accented letters to plain
ones (Unicode NFKD decomposition, dropping the combining marks, and the Turkish dotless *ı* to *i*), so
*Yırtıcı*, *YIRTICI* and *yirtici* all become the term `yirtici`. Because the indexer and the ranker share the
same function, the index was rebuilt once after this change.

## Speed

The ranking query reads only the postings of the query terms. A covering index on
`postings(term_id) INCLUDE (page_id, tf)` lets PostgreSQL answer it from the index alone, without reading the
table. The table below is the database time of the 20 test queries on the full collection (4,697 pages,
1,458,705 postings), measured inside Supabase on 2 November 2026, second run of each query:

| Query | Pages scored by `rank()` | `rank()` (ms) | Pages shown (all words) | Search page (ms) |
| --- | ---: | ---: | ---: | ---: |
| Q01 inverted index | 751 | 2.1 | 81 | 1.6 |
| Q02 tf idf term weighting | 1,122 | 2.6 | 38 | 1.7 |
| Q03 cosine similarity vector space model | 1,786 | 3.6 | 11 | 2.3 |
| Q04 precision and recall | 454 | 1.7 | 77 | 1.4 |
| Q05 web crawler politeness robots | 2,052 | 3.6 | 5 | 2.1 |
| Q06 pagerank link analysis | 1,214 | 2.7 | 17 | 1.7 |
| Q07 stemming and lemmatization | 143 | 1.4 | 13 | 1.1 |
| Q08 python list comprehension | 1,686 | 3.4 | 62 | 2.2 |
| Q09 reading and writing files in python | 2,096 | 4.0 | 214 | 2.9 |
| Q10 handling exceptions try except | 1,513 | 3.1 | 234 | 2.4 |
| Q11 regular expressions | 913 | 2.4 | 277 | 2.4 |
| Q12 css flexbox layout | 498 | 1.8 | 6 | 1.2 |
| Q13 javascript click event listener | 1,254 | 2.8 | 38 | 1.8 |
| Q14 aria roles accessibility | 1,574 | 3.2 | 71 | 2.1 |
| Q15 create index b-tree postgresql | 2,558 | 4.4 | 23 | 2.6 |
| Q16 jsonb operators | 1,205 | 2.6 | 5 | 1.6 |
| Q17 scrapy item pipeline | 595 | 2.0 | 29 | 1.4 |
| Q18 flask blueprints | 86 | 1.3 | 21 | 1.1 |
| Q19 albert einstein quotes | 356 | 1.6 | 8 | 1.2 |
| Q20 sapiens brief history of humankind | 932 | 2.4 | 3 | 1.5 |

Every query takes under 5 ms in the database (median 2.6 ms for `rank()`), far below the 0.5-second target.
Each of the 20 queries finds at least three pages that contain all of its words. The time a user waits is
therefore dominated by the network between the web server and the database, not by the ranking: the search page
needs two database round trips per query (see the indexing section).

## Testing

`tests/test_rank.py` contains the worked example above with exact scores and order for both queries, and checks
that `k` limits the results, that a query identical to a page scores 1, that unknown words are ignored, and that
empty, punctuation-only, number-only and stop-word-only queries return `[]`. Each test runs on an in-memory
version of the `terms`, `postings` and `page_norms` tables built by the indexer's own code. When the variable
`IRIS_TEST_DATABASE_URL` is set, the same tests also run the real SQL of `rank()` on PostgreSQL, using temporary
tables that never touch the shared index.
`tests/test_search_filters.py` checks the search-page rules: only pages with every query word, no results for a
word that is not in the collection, the site filter, the title bonus, and that the `/explain` page and the fast
search query give exactly the scores of `rank()`. `tests/test_preprocess.py` checks the folding of Turkish and
accented letters.

## Limitations and Possible Improvements

- **Raw term frequency.** A page that repeats a word 50 times gets 50 times its weight for that word. A
  logarithmic term frequency, $1 + \ln \mathrm{tf}$, would damp this (Manning et al., 2008, §6.4.1).
- **Title only as a bonus.** The title adds a fixed bonus of up to 0.1 but is not part of the TF-IDF vector;
  indexing the title as its own weighted field would be a cleaner model.
- **No phrase or proximity information.** *Inverted index* and *index inverted* give the same scores.
- **All words required.** The search page hides pages that contain only some of the query words. This is what
  users expect for short queries, but a long, specific query can then return nothing; a fallback that shows
  partial matches below a separator would help.
- **Alternatives.** BM25 (Robertson & Zaragoza, 2009) usually ranks better than plain TF-IDF and could replace
  the weighting without changing the index tables.

## References

Manning, C. D., Raghavan, P., & Schütze, H. (2008). *Introduction to information retrieval*. Cambridge University Press.

Robertson, S., & Zaragoza, H. (2009). The probabilistic relevance framework: BM25 and beyond. *Foundations and Trends in Information Retrieval, 3*(4), 333–389.

Salton, G., & Buckley, C. (1988). Term-weighting approaches in automatic text retrieval. *Information Processing & Management, 24*(5), 513–523.
