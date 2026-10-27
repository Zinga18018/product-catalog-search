# README visual: held-out ranking diagnostic

The [SVG figure](figures/heldout-ranking.svg) is generated from the repository's actual evaluation, not invented measurements or a UI screenshot. Its solid background, high-contrast labels, embedded SVG title/description, and README alt text keep it readable on light and dark GitHub pages. Open the image for a larger view on small screens.

## What it shows

TF-IDF and BM25 produce the same first-relevant rank and recall on each of the 19 answerable held-out queries. The chart combines those identical counts instead of suggesting that one method wins. It does not claim their complete rankings are identical.

| First relevant product | Queries, per method |
| --- | ---: |
| Rank 1 | 17 |
| Rank 2 | 1 |
| Rank 3 | 0 |
| Rank 4 | 1 |
| Rank 5 | 0 |
| Absent from top 5 | 0 |

The two non-first-place cases are shown verbatim from the evaluation and catalog:

- **T02: `charge laptop away from wall outlet`** — both methods rank the wall charger first and the labelled relevant power bank second.
- **T05: `keep coffee warm on commute`** — both methods rank the reading lamp first and the labelled relevant travel mug fourth.

MRR@5 is `0.9342105263157895`, and Recall@5 is `1.0`, averaging only the 19 answerable queries. The remaining held-out query has no labelled answer; both methods return no results. That single example is reported separately and cannot establish reliable rejection performance.

All 54 products and 30 query judgments are synthetic and author-created. This tiny, familiar catalog is not an independent benchmark, user study, or production evaluation. See [data provenance](../data/README.md) and [the complete evaluation](../results/evaluation.json), including the development split.

## Reproduce or check

From the repository root, using Python 3.11+:

```sh
python -m catalog_search.evaluate --check
python scripts/render_readme_visual.py
python scripts/render_readme_visual.py --check
python -m unittest discover -s tests -v
```

The generator uses only the Python standard library; no Plotly, browser, external fonts, API keys, network calls, or new runtime dependencies are required. It recomputes the evaluation and refuses to render if the checked-in JSON or CSV differs. It also validates the shared-metric assumption and fails explicitly if the two-case layout needs revision. This prevents a changed dataset from silently retaining an outdated story.

The generated [provenance manifest](figures/heldout-ranking.provenance.json) records SHA-256 hashes of the catalog, judgments, ranker, evaluator, JSON/CSV evidence, and drawing script. It deliberately omits timestamps, so exact regeneration is stable.

## Verification performed on 2026-10-27

- Public source baseline: `3351a3480b5bb230912f6602994a07bb92e0e225` on `Zinga18018/product-catalog-search/main`. All 24 remote files matched the local baseline before editing.
- Evaluation JSON/CSV matched exact recomputation; no labels or ranker settings were changed.
- SVG was rendered locally with installed librsvg/Cairo and visually inspected. This is an image render, not application/browser QA.
- Figure source/provenance recomputation and unit/HTTP integration tests were rerun after adding the visual.

Publication and GitHub rendering are separate checks; this local note does not by itself establish a successful remote publication.
