# Software Requirements Specification (SRS) - IRIS Search Engine

This document outlines the functional and non-functional requirements for the IRIS search engine project. These metrics serve as the baseline for implementation, code reviews, and testing phases.

---

## 1. Functional Requirements (FR)
Functional requirements describe the specific actions, behaviors, and operations each module of the IRIS pipeline must execute.

### 1.1 Web Crawler Module
* **FR-1.1:** The crawler must accept a predefined list of seed URLs and extract clean text, page titles, URLs, and crawl dates.
* **FR-1.2:** The crawler must adhere strictly to the rules of `robots.txt` (RFC 9309) for each target website.
* **FR-1.3:** The crawler must implement a rate-limiting delay between consecutive requests to avoid overwhelming target servers.
* **FR-1.4:** The system must restrict the crawl size to a target depth and a capacity constraint of 1,000 to 5,000 pages.
* **FR-1.5:** The crawler must detect and skip duplicate URLs or unchanged pages to prevent redundant database entries.

### 1.2 Text Pre-Processing Module
* **FR-2.1:** The system must break raw web page text down into individual words (tokenization).
* **FR-2.2:** The text engine must normalize text by converting all tokens into lowercase format.
* **FR-2.3:** The system must drop common stop words (e.g., "the", "and") from the token stream.
* **FR-2.4:** The system must reduce words to their grammatical root form (stemming) using NLTK or spaCy.

### 1.3 Indexer Module
* **FR-3.1:** The system must build an inverted index mapping each unique term to its corresponding hosting pages and structural frequency.
* **FR-3.2:** The indexer must parse new database entries, apply the shared pre-processing function, and populate the system's `postings` data layout.

### 1.4 Ranker (TF-IDF) Module
* **FR-4.1:** The system must calculate TF-IDF weights based on term frequency within a page relative to document frequency across the corpus.
* **FR-4.2:** The ranking engine must evaluate the mathematical similarity between user queries and indexed pages using Cosine Similarity.
* **FR-4.3:** The application must return the top-k relevant search results ordered by their structural relevance scores.

### 1.5 Query Processing & Web Interface
* **FR-5.1:** The web interface must present a clean landing page featuring a primary search input box.
* **FR-5.2:** The query processor must pass user input through the identical pre-processing routine used during index generation.
* **FR-5.3:** The results page must display a clean matching list showcasing the Title, hyperlinked URL, and a contextual short snippet for each top result.
* **FR-5.4:** The interface must elegantly handle multi-page navigation (pagination) and explicitly show a "no results found" state when appropriate.

---

## 2. Non-Functional Requirements (NFR)
Non-functional requirements specify the performance thresholds, operational limitations, quality attributes, and architectural constraints of the IRIS system.

### 2.1 Performance & Efficiency
* **NFR-1 (Search Latency):** The Flask backend and API must parse queries and return JSON responses in under 1.0 second.
* **NFR-2 (Optimization):** The PostgreSQL database must utilize optimized database indexes and cache IDF calculations to keep query speeds stable.

### 2.2 Project Scope & Constraints
* **NFR-3 (Data Restrictions):** The scope of the indexing pipeline is strictly constrained to text processing; indexing of rich multimedia (images and video) is omitted.
* **NFR-4 (Architecture Limits):** The system must execute as a localized pipeline; distributed web crawling and real-time index streaming are out of scope.
* **NFR-5 (Open-Source Stack):** The entire code pipeline must be written in Python and rely strictly on free, open-source utilities (Scrapy, PostgreSQL, Flask, NLTK/spaCy).

### 2.3 Quality, Testing, & Usability
* **NFR-6 (Test Verification):** Every distinct code module must pass designated unit tests, and the complete search workflow must successfully fulfill end-to-end integration tests.
* **NFR-7 (Validation Metrics):** The scoring system must maintain measurable accuracy benchmarked against a custom test set of 20 sample queries evaluated using Precision@10 metrics.
* **NFR-8 (UI Responsiveness):** The Flask web interface must load, render, and remain completely readable inside standard desktop web browsers.

---

## 3. Implementation Tracking Dashboard

- [ ] **FR-1.1 to 1.5:** Web Crawler Pipeline Completed
- [ ] **FR-2.1 to 2.4:** Tokenization & Stemming Shared Function
- [ ] **FR-3.1 to 3.2:** Inverted Index Engine & Schema Build
- [ ] **FR-4.1 to 4.3:** Cosine Similarity & TF-IDF Vector Math
- [ ] **FR-5.1 to 5.4:** Flask API Routing & Frontend Snippet Interface
- [ ] **NFR-1 & NFR-2:** Latency Verification (< 1s Response) and Index Tuning
- [ ] **NFR-6 & NFR-7:** Pipeline System Testing & Precision@10 Evaluation
