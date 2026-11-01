# Evaluation Test Queries

Owner: Yazen (AI Engineer) · Requirement: NFR-7 (Precision@10 over 20 queries) · Machine-readable copy: [`test-queries.json`](test-queries.json)

The 20 queries cover all 9 sites in the collection. Each one names at least one page that answers it
(**known relevant page**, matched by a part of its URL). `Terms` is the real output of `preprocess(query)`,
so it is exactly what the ranker searches for.

## Check that every query has a relevant page in our collection

```bash
python3 -m ranker.check_queries --out docs/test-queries-check.md
```

For each query it prints how many pages in the `pages` table match the known relevant URLs, where the first
of them ranks in the top 10, and how long `rank()` took. A query with **0** relevant pages must be fixed
(add another URL part that is in the collection) or replaced, and the change noted below.

## Queries

| ID | Query | Terms | Sites | Relevant if the page… | Known relevant page (URL contains) |
| --- | --- | --- | --- | --- | --- |
| Q01 | inverted index | `invert index` | ir-book, wikipedia | Explains what an inverted index is or how one is built. | `a-first-take-at-building-an-inverted-index-1.html`<br>`/wiki/Inverted_index` |
| Q02 | tf idf term weighting | `tf idf term weight` | ir-book, wikipedia | Defines TF-IDF or explains tf / idf weighting. | `tf-idf-weighting-1.html`<br>`/wiki/Tf%E2%80%93idf`<br>`/wiki/Tf–idf` |
| Q03 | cosine similarity vector space model | `cosin similar vector space model` | ir-book, wikipedia | Explains the vector space model or cosine scoring. | `dot-products-1.html`<br>`/wiki/Cosine_similarity`<br>`/wiki/Vector_space_model` |
| Q04 | precision and recall | `precis recal` | ir-book, wikipedia | Defines precision and recall or uses them for evaluation. | `/wiki/Precision_and_recall`<br>`evaluation-of-unranked-retrieval-sets-1.html` |
| Q05 | web crawler politeness robots | `web crawler polit robot` | ir-book, wikipedia | How crawlers work, especially politeness and robots.txt. | `/wiki/Web_crawler`<br>`/wiki/Robots.txt`<br>`/IR-book/html/htmledition/crawling-1.html` |
| Q06 | pagerank link analysis | `pagerank link analysi` | ir-book, wikipedia | PageRank or link-analysis ranking. | `/wiki/PageRank`<br>`/IR-book/html/htmledition/pagerank-1.html` |
| Q07 | stemming and lemmatization | `stem lemmat` | ir-book, wikipedia | Stemming or lemmatisation as text normalisation. | `stemming-and-lemmatization-1.html`<br>`/wiki/Stemming`<br>`/wiki/Lemmatisation` |
| Q08 | python list comprehension | `python list comprehens` | python-docs | Explains or shows Python list comprehensions. | `/tutorial/datastructures.html` |
| Q09 | reading and writing files in python | `read write file python` | python-docs | Opening, reading and writing files in Python. | `/tutorial/inputoutput.html` |
| Q10 | handling exceptions try except | `handl except tri except` | python-docs | Errors and exception handling with try / except. | `/tutorial/errors.html` |
| Q11 | regular expressions | `regular express` | python-docs, mdn | Regular expressions: Python re, JavaScript RegExp, or the concept. | `/library/re.html`<br>`/howto/regex.html`<br>`Guide/Regular_expressions` |
| Q12 | css flexbox layout | `css flexbox layout` | mdn | CSS flexible box layout (display: flex). | `flexible_box_layout`<br>`/CSS/flex` |
| Q13 | javascript promises async await | `javascript promis async await` | mdn | Promises or async / await in JavaScript. | `Global_Objects/Promise`<br>`async_function`<br>`Using_promises` |
| Q14 | http status code not found | `http statu code found` | mdn | HTTP response status codes, e.g. 404 Not Found. | `Status/404`<br>`/HTTP/Status`<br>`/HTTP/Reference/Status` |
| Q15 | create index b-tree postgresql | `creat index b tree postgresql` | postgresql-docs | Creating indexes / B-tree index types in PostgreSQL. | `sql-createindex.html`<br>`indexes-types.html` |
| Q16 | jsonb operators | `jsonb oper` | postgresql-docs | PostgreSQL JSON / JSONB types or operators. | `functions-json.html`<br>`datatype-json.html` |
| Q17 | scrapy item pipeline | `scrapi item pipelin` | scrapy-docs | Scrapy item pipelines. | `/topics/item-pipeline.html` |
| Q18 | flask blueprints | `flask blueprint` | flask-docs | Flask blueprints. | `/blueprints/` |
| Q19 | albert einstein quotes | `albert einstein quot` | quotes | Quotes by Albert Einstein or his author page. | `/author/Albert-Einstein` |
| Q20 | sapiens brief history of humankind | `sapien brief histori humankind` | books | The book page for Sapiens: A Brief History of Humankind. | `sapiens-a-brief-history-of-humankind` |

**Mix.** IR topics (Q01–Q07) are covered by both the IR book and Wikipedia; Q08–Q16 target the programming and
database documentation; Q17–Q20 are short "known item" searches for one specific page. Q11 is ambiguous on
purpose: relevant pages exist on two sites. Numbers are removed by `preprocess()`, so Q14 searches the words
of "404 Not Found", not the number.

## Judging relevance (Precision@10)

1. Run each query on the search page and take the **top 10** results.
2. For each result, open the page and mark it **1** (relevant) or **0** using only the "Relevant if the page…"
   column. Do not look at the score.
3. Two members judge each query independently; disagreements are discussed and the agreed label is stored in
   `judgments` in `test-queries.json` (`{"<page_id>": 1}`).
4. **Precision@10** = relevant results in the top 10 ÷ 10. The system score is the mean over the 20 queries.

Do not change a query after seeing its results. If a query must be replaced, write the old query, the new one
and the reason here.

## Changes

- *(none yet)*
