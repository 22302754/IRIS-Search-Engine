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

## Testing

`tests/test_rank.py` contains the worked example above with exact scores and order for both queries, and checks
that `k` limits the results, that a query identical to a page scores 1, that unknown words are ignored, and that
empty, punctuation-only, number-only and stop-word-only queries return `[]`. Each test runs on an in-memory
version of the `terms`, `postings` and `page_norms` tables built by the indexer's own code. When the variable
`IRIS_TEST_DATABASE_URL` is set, the same tests also run the real SQL of `rank()` on PostgreSQL, using temporary
tables that never touch the shared index.

## Limitations and Possible Improvements

- **Raw term frequency.** A page that repeats a word 50 times gets 50 times its weight for that word. A
  logarithmic term frequency, $1 + \ln \mathrm{tf}$, would damp this (Manning et al., 2008, §6.4.1).
- **Title not used.** Only the page text is indexed; a match in the page title counts the same as one in the
  body. Indexing the title, possibly with a higher weight, is a simple improvement.
- **No phrase or proximity information.** *Inverted index* and *index inverted* give the same scores.
- **Response time.** The verified API call on 1 November took 3,183 ms (see the indexing section), above the
  1-second target. Common query words have long postings lists; measuring the 20 test queries will show
  whether caching $N$ and the IDF values, or limiting very common terms, is needed.
- **Alternatives.** BM25 (Robertson & Zaragoza, 2009) usually ranks better than plain TF-IDF and could replace
  the weighting without changing the index tables.

## References

Manning, C. D., Raghavan, P., & Schütze, H. (2008). *Introduction to information retrieval*. Cambridge University Press.

Robertson, S., & Zaragoza, H. (2009). The probabilistic relevance framework: BM25 and beyond. *Foundations and Trends in Information Retrieval, 3*(4), 333–389.

Salton, G., & Buckley, C. (1988). Term-weighting approaches in automatic text retrieval. *Information Processing & Management, 24*(5), 513–523.
