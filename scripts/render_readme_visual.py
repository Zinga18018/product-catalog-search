"""Plot the checked synthetic evaluation with Matplotlib (optional dev dependency).

Run from any directory. --check renders again and compares exact SVG bytes;
--verify checks data, source hashes and saved SVG integrity without Matplotlib.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
from html import escape
import io
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from catalog_search.evaluate import evaluate, render_csv  # noqa: E402

DEST = ROOT / "docs" / "figures"
PLOT_VERSION = "3.10.8"


def checked_report():
    report = evaluate()
    expected = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if (ROOT / "results/evaluation.json").read_text(encoding="utf-8") != expected:
        raise ValueError("Evaluation JSON is stale; regenerate and review it first.")
    if (ROOT / "results/per-query.csv").read_text(encoding="utf-8") != render_csv(report):
        raise ValueError("Evaluation CSV is stale; regenerate and review it first.")
    return report


def chart_data(report):
    rows = [r for r in report["per_query"] if r["split"] == "heldout"]
    methods = {m: [r for r in rows if r["method"] == m] for m in ("tfidf", "bm25")}
    for a, b in zip(methods["tfidf"], methods["bm25"], strict=True):
        fields = ("id", "reciprocal_rank_at_k", "recall_at_k", "false_positive_no_answer")
        if tuple(a[f] for f in fields) != tuple(b[f] for f in fields):
            raise ValueError("Methods no longer tie per query; use separate series.")
    answerable = [r for r in methods["tfidf"] if r["relevant_ids"]]
    counts = Counter(round(1 / r["reciprocal_rank_at_k"]) if r["reciprocal_rank_at_k"] else 0 for r in answerable)
    n, k = len(answerable), report["k"]
    assert sum(counts.values()) == report["splits"]["heldout"]["answerable_queries"]
    if k != 5 or n != 19:
        raise ValueError("Review axis settings for changed query count or cutoff.")
    return {"n": n, "k": k, "ranks": [1, 2, 3, 4, 5, 0],
            "counts": [counts[r] for r in [1, 2, 3, 4, 5, 0]],
            "mrr": report["splits"]["heldout"]["tfidf"]["mrr_at_k"],
            "recall": report["splits"]["heldout"]["tfidf"]["recall_at_k"]}


def figure(report, png_path=None):
    data = chart_data(report)
    try:
        import matplotlib
    except ImportError as exc:
        raise SystemExit("Install requirements-visuals.txt to render; --verify is standard-library only.") from exc
    if matplotlib.__version__ != PLOT_VERSION:
        raise SystemExit(f"Exact reproduction uses matplotlib=={PLOT_VERSION}; found {matplotlib.__version__}.")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    with matplotlib.rc_context({"font.family": "DejaVu Sans", "font.size": 10,
                                "svg.fonttype": "none", "svg.hashsalt": "catalog-rank-count-v1",
                                "figure.facecolor": "white", "axes.facecolor": "white"}):
        fig, ax = plt.subplots(figsize=(6.4, 3.9), dpi=100)
        fig.subplots_adjust(left=0.22, right=0.86, bottom=0.18, top=0.79)
        fig.text(0.04, 0.95, "First relevant result by rank", fontsize=12, weight="bold", va="top")
        fig.text(0.04, 0.885, "TF-IDF and BM25: same counts on 19 answerable held-out queries", fontsize=9, va="top")
        positions = list(range(6))
        bars = ax.barh(positions, data["counts"], height=0.58, color="#5b6c7a", zorder=3)
        for rank, bar in zip(data["ranks"], bars, strict=True):
            bar.set_gid(f"rank-{rank}")
        ax.set_yticks(positions, [f"Rank {r}" if r else "Not in top 5" for r in data["ranks"]])
        ax.invert_yaxis()
        ax.set_xlim(0, 19)
        ax.set_xticks([0, 5, 10, 15, 19])
        ax.set_xlabel("Number of synthetic queries", labelpad=10)
        ax.xaxis.grid(True, color="#e2e2e2", linewidth=0.7)
        ax.tick_params(axis="both", length=0, pad=8, labelsize=10)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color("#888888")
        for y, count in zip(positions, data["counts"], strict=True):
            ax.text(20, y, f"{count}/19", va="center", fontsize=10, clip_on=False)
        output = io.StringIO()
        fig.savefig(output, format="svg", metadata={"Date": None, "Creator": f"Matplotlib {PLOT_VERSION}"})
        if png_path:
            fig.savefig(png_path, format="png", dpi=150, metadata={"Software": f"Matplotlib {PLOT_VERSION}"})
        plt.close(fig)
    description = ("Both TF-IDF and BM25 have the same first-relevant ranks on 19 answerable synthetic held-out queries: "
                   + ", ".join(f"rank {r}: {v}" if r else f"not in top 5: {v}" for r, v in zip(data["ranks"], data["counts"], strict=True))
                   + ". Author-created labels; not an independent benchmark. Complete rankings can differ.")
    # Accessibility metadata only; all plotted geometry is produced by Matplotlib.
    svg = re.sub(r"(<svg\b[^>]*)(>)", lambda m: m.group(1) + ' role="img" aria-labelledby="title desc">'
                 + '<title id="title">First relevant result by rank</title><desc id="desc">'
                 + escape(description) + "</desc>", output.getvalue(), count=1)
    return svg


def provenance(report, svg):
    inputs = ["catalog_search/evaluate.py", "catalog_search/engine.py", "data/catalog.json", "data/queries.json",
              "results/evaluation.json", "results/per-query.csv", "scripts/render_readme_visual.py", "requirements-visuals.txt"]
    return {"schema_version": 2, "figure": "heldout-ranking.svg", "renderer": f"Matplotlib {PLOT_VERSION}; Agg backend",
            "chart_data": chart_data(report), "svg_sha256": sha256(svg.encode()).hexdigest(),
            "scope": "19 answerable held-out synthetic author-labelled queries; no-answer query reported separately",
            "source_sha256": {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in inputs}}


def artifacts(png_path=None):
    report = checked_report()
    svg = figure(report, png_path)
    return {"heldout-ranking.svg": svg,
            "heldout-ranking.provenance.json": json.dumps(provenance(report, svg), indent=2) + "\n"}


def verify_saved():
    """Standard-library integrity and numeric-data check; does not rerender."""
    report = checked_report()
    svg = (DEST / "heldout-ranking.svg").read_text(encoding="utf-8")
    saved = json.loads((DEST / "heldout-ranking.provenance.json").read_text(encoding="utf-8"))
    if saved != provenance(report, svg):
        raise ValueError("Saved visual/provenance differs from current data, source, or SVG bytes.")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Rerender with pinned Matplotlib and compare bytes")
    parser.add_argument("--verify", action="store_true", help="Check saved data/hashes without plotting dependencies")
    parser.add_argument("--png", type=Path, help="Also render a PNG review copy at this path")
    args = parser.parse_args()
    if args.verify:
        verify_saved()
        print("Saved SVG, source hashes, and numeric data verified (no rerender).")
        return
    files = artifacts(args.png)
    if args.check:
        for name, content in files.items():
            if not (DEST / name).is_file() or (DEST / name).read_text(encoding="utf-8") != content:
                raise SystemExit(f"Stale visual: {DEST / name}. Regenerate and inspect before committing.")
        print("Matplotlib SVG and provenance match exact recomputation.")
    else:
        DEST.mkdir(parents=True, exist_ok=True)
        for name, content in files.items():
            (DEST / name).write_text(content, encoding="utf-8", newline="\n")
        print("Generated Matplotlib plot and provenance from checked evaluation.")


if __name__ == "__main__":
    main()
