# Local verification record

Verified on 2026-10-26 using Python 3.14.7 and Node.js 24.19.0 on Windows. This record describes checks actually run during construction. GitHub Actions has not run and no public service is hosted.


| Check | Actual outcome |
| --- | --- |
| `python -W error::ResourceWarning -m unittest discover -s tests -v` | 15 tests passed, including concurrent live HTTP requests on ephemeral loopback ports |
| `python -m compileall -q catalog_search tests` | Passed |
| `node --check static/app.js` | Passed |
| `python -m catalog_search.evaluate --check` | Stored JSON/CSV matched exact recomputation |
| Local Chrome desktop UI | Catalog browsing, comparison, category/budget filters, and expanded score contributions inspected |
| Empty result UI | `garden hose` returned zero matches in both lists |
| Invalid range UI | Minimum 40 / maximum 30 showed a clear validation message |
| Responsive UI | 390 × 844 viewport inspected; stacked controls/content, document width 375 with a 375-pixel client width (no horizontal overflow) |
| Browser console | No warning/error messages during the inspected search interaction |

The initial sandbox blocked loopback client sockets. HTTP tests passed when run with reviewed loopback access; no public endpoint was involved. A code review found Decimal-context rounding could accept overly precise malformed price strings. Exact format validation and regression cases now reject those strings and exponent notation before arithmetic.

## Recorded quality and failure cases

Both methods produced held-out MRR@5 `0.9342105263157895` and Recall@5 `1.0` across 19 answerable queries. Each split contains only one no-answer query; both were rejected. See the complete [JSON](../results/evaluation.json) and [CSV](../results/per-query.csv), including hashes of the frozen inputs.

Two held-out intents expose lexical weaknesses: T02 (`charge laptop away from wall outlet`) places a wall charger before the relevant power bank; T05 (`keep coffee warm on commute`) places a reading lamp before the relevant travel mug, which appears fourth. Ranking does not understand exclusion or intent merely because a query is natural language. The methods differ in some lower ranks but tie on the aggregate metrics. No held-out labels or ranker parameters were changed after seeing those results.

## Publication boundary

Local project work is complete. Repository creation/push is pending verified access to the intended owner, Zinga18018. No public repository was created through another account. A public 404 response for the proposed name is not proof that an inaccessible private repository does not exist; check collision again under the authenticated target owner before creating a public repository.

No tokens, API keys, paid services, model downloads, or hosting resources are needed to run this project. Commit dates should remain the actual creation dates.
