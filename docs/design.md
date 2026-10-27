# Developer decisions

## Scope

Use a small standard-library Python application and a vanilla browser UI so a reader can run the whole demo without a package manager or external service. The complete catalog fits in memory. A search scans eligible documents rather than introducing a database or vector store whose operational cost would dominate this example.

Dense semantic search was considered. Three existing interpreters on the development host had no Torch, Transformers, Sentence Transformers, or ONNX Runtime. Cached MiniLM weights alone are insufficient to run retrieval. No inference package or model was installed or downloaded; `/api/meta` and the UI explicitly report semantic retrieval as unavailable. BM25 is an actual alternative ranking algorithm, not an embedding simulation.

## Index and scoring

Each document is the title, category, description, and tags concatenated once. Tokenization uses Unicode NFKC normalization, case folding, alphanumeric Unicode words, and a fixed small stop-word list in `engine.py`. There is no field boosting or stemming. Prices are excluded from document text.

For `N` documents and document frequency `df(t)`, the TF-IDF baseline uses `idf(t) = log((N+1)/(df(t)+1)) + 1` and sublinear frequency `1 + log(tf)`. Document and query vectors use those weights and cosine similarity. Out-of-vocabulary query terms do not enter the vector. An explanation lists each term's normalized contribution; these sum to the score.

BM25 uses `idf(t) = log(1 + (N-df(t)+0.5)/(df(t)+0.5))`, `k1=1.2`, and `b=0.75`. Each distinct query term contributes:

```text
idf(t) * tf(t,d) * (k1+1)
-----------------------------------------------
tf(t,d) + k1 * (1-b + b * length(d)/average_length)
```

Query term repetition is ignored for BM25. Parameters are conventional fixed values, not fitted to these labels. The explanation is the exact term sum. Index statistics use the entire catalog consistently even with filters. Stable product IDs break score ties. Only positive lexical scores are returned for nonblank queries. A truly blank query browses; punctuation-only or stop-word-only queries return no matches.

## Input and money rules

Prices are stored as integer cents. The request accepts nonnegative decimal USD values with at most two fractional digits (no exponent notation), validates the exact textual representation, then converts them with `Decimal`, so floating-point and decimal-context rounding do not control boundaries. Both limits are inclusive. Invalid/nonfinite prices, inverted bounds, and unknown categories return HTTP 400.

Queries are limited to 256 characters and 32 searchable tokens; control characters are rejected. Result limits are integers from 1 to 50. Unknown or repeated request parameters are rejected. Queries are data, never SQL, shell text, regular expressions, or executable browser markup. The browser builds result content with DOM `textContent`; no external fonts, analytics, images, or scripts load.

## API

`GET /api/meta` returns catalog count, category slugs, method descriptions, semantic availability, and the checked-in evaluation report if present.

`GET /api/search?q=lamp&method=bm25&category=home&min_price=10&max_price=50&limit=8`

All parameters are optional. Defaults are an empty query, `tfidf`, no filters, and eight results. A response includes the normalized query, method, matching count before the limit, applied price bounds in cents, and products with a score, matched terms, and exact term contributions. Blank-browse scores are JSON null. Missing paths return JSON 404; validation errors return JSON 400 with an `error` message. `/`, `/app.js`, and `/styles.css` are explicit routes; arbitrary filesystem paths are never served.

## Evaluation choices

The separate data-writing task froze judgments before ranking results were produced. Splits are stored with query IDs and rationale in JSON. The evaluator validates IDs, uniqueness, splits, and filter compatibility before computing MRR@5 and Recall@5. Empty relevance sets are excluded from answerable metrics and measured separately. The report contains complete per-query rankings and raw-data hashes, and CI verifies exact recomputation. No wall-clock timing, throughput, confidence intervals, or production inference is claimed.

The current held-out result does not separate the algorithms on these aggregate metrics. It demonstrates that a real comparator and reproducible evaluation exist; it does not justify preferring BM25. Future work should first collect more diverse, independently judged queries, including hard no-answer and multi-relevant cases. Keep a new final test set untouched while tuning on development queries.

## Security and operations boundary

The app binds to `127.0.0.1` by default, handles only read requests, and keeps no query log beyond the standard HTTP access line (path/query in terminal output). Do not send private query text if terminal logs are being shared. Responses use a restrictive same-origin content policy and `nosniff`. The thread-per-request standard-library server, lack of request-rate controls, and local file-backed data are suitable for a local demonstration. Production operation requires a separate design.

## Provenance

The implementation, synthetic catalog, labels, tests, and documentation were created with Codex assistance for a new project in October 2026. Review the code and data before making portfolio claims. New Git history must retain actual current dates; this project provides no evidence of earlier work, unassisted authorship, or professional deployment.
