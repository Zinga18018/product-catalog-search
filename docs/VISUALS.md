# Ranking plot source

[The plot](figures/heldout-ranking.svg) reads the checked-in [evaluation JSON](../results/evaluation.json), verified against a fresh evaluation before rendering. Both methods have the same first-relevant rank on all 19 answerable held-out queries: 17 at rank 1, one at rank 2, and one at rank 4. Their full rankings can differ.

The two non-first-place results are:

| Query | First result | Labelled relevant result |
| --- | --- | --- |
| `charge laptop away from wall outlet` | Compact 65W USB-C Charger | Roam 20000 USB-C Power Bank, rank 2 |
| `keep coffee warm on commute` | Warmglow Reading Lamp | Lidded Commuter Travel Mug, rank 4 |

The separate no-answer query returns no results for both methods; one example does not establish rejection reliability. All products and judgments are synthetic and author-created, not an independent benchmark. See [data provenance](../data/README.md).

## Reproduce

Python 3.11+. The application and numeric integrity tests use the standard library. Plot regeneration separately requires the pinned Matplotlib version:

```sh
python -m pip install -r requirements-visuals.txt
python -m catalog_search.evaluate --check
python scripts/render_readme_visual.py
python scripts/render_readme_visual.py --check
# Numeric and saved-file integrity check without Matplotlib:
python scripts/render_readme_visual.py --verify
python -m unittest discover -s tests -v
```

The [provenance file](figures/heldout-ranking.provenance.json) records the plotted counts, Matplotlib version and SHA-256 hashes of the inputs, plotting script and SVG. The script calls Matplotlib's `barh` on the evaluated counts using the Agg backend. It rejects stale inputs or a mismatch in per-query metrics. Fixed SVG metadata, text fonts and hash salt make regeneration deterministic with Matplotlib 3.10.8. `--verify` checks numeric data and file integrity; only `--check` actually rerenders. CI's standard-library tests use the former.

This presentation-only revision starts from commit `f4f90d5ec3269e775d5d9d3141f48ff9632ad777`. No products, labels, rankings, or evaluation settings changed. The SVG uses a fixed white background and contains accessible text, with no external assets.
