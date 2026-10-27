"""Render the README diagnostic from exactly recomputed synthetic evaluation data.

Standard library only. Run from any directory; use --check to detect stale files.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from catalog_search.evaluate import evaluate, render_csv  # noqa: E402

DEST = ROOT / "docs" / "figures"


def checked_report():
    report = evaluate()
    expected = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if (ROOT / "results/evaluation.json").read_text(encoding="utf-8") != expected:
        raise ValueError("Evaluation JSON is stale; regenerate and review it first.")
    if (ROOT / "results/per-query.csv").read_text(encoding="utf-8") != render_csv(report):
        raise ValueError("Evaluation CSV is stale; regenerate and review it first.")
    return report


def figure(report):
    rows = [r for r in report["per_query"] if r["split"] == "heldout"]
    methods = {m: [r for r in rows if r["method"] == m] for m in ("tfidf", "bm25")}
    first = methods["tfidf"]
    for a, b in zip(first, methods["bm25"], strict=True):
        if (a["id"], a["reciprocal_rank_at_k"], a["recall_at_k"], a["false_positive_no_answer"]) != (
            b["id"], b["reciprocal_rank_at_k"], b["recall_at_k"], b["false_positive_no_answer"]
        ):
            raise ValueError("Methods no longer tie per query; redesign this shared-rank figure.")
    answerable = [r for r in first if r["relevant_ids"]]
    counts = Counter(round(1 / r["reciprocal_rank_at_k"]) if r["reciprocal_rank_at_k"] else 0 for r in answerable)
    assert sum(counts.values()) == report["splits"]["heldout"]["answerable_queries"]
    failures = [r for r in answerable if r["reciprocal_rank_at_k"] not in (0, 1)]
    no_answer = [r for r in first if not r["relevant_ids"]]
    # These deliberate layout constraints fail visibly if a new dataset needs a new story.
    if len(failures) != 2 or len(no_answer) != 1 or any(len(r["relevant_ids"]) != 1 for r in failures):
        raise ValueError("The two-case diagnostic layout needs review for these new results.")
    for row in failures:
        other = next(r for r in methods["bm25"] if r["id"] == row["id"])
        if row["top_ids"][0] != other["top_ids"][0]:
            raise ValueError("Failure-case first results differ; update the figure layout.")
    catalog = {p["id"]: p for p in json.loads((ROOT / "data/catalog.json").read_text())}
    k = report["k"]
    if k != 5:
        raise ValueError("This five-rank layout needs review for a new cutoff.")
    n = len(answerable)
    mrr = report["splits"]["heldout"]["tfidf"]["mrr_at_k"]
    recall = report["splits"]["heldout"]["tfidf"]["recall_at_k"]
    desc = (f"On {n} answerable held-out queries, both TF-IDF and BM25 have the same first-relevant ranks: "
            + ", ".join(f"rank {i}: {counts[i]}" for i in range(1, k + 1))
            + f"; absent from top {k}: {counts[0]}. MRR@{k} {mrr:.4f}; Recall@{k} {recall:.4f}. "
            "This is a tiny synthetic author-labelled demo, not an independent benchmark or evidence of method superiority.")
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="640" height="860" viewBox="0 0 640 860" role="img" aria-labelledby="title desc">',
           '<title id="title">Product Catalog Search: shared ranks and lexical failure cases</title>',
           f'<desc id="desc">{escape(desc)}</desc>',
           '<rect width="640" height="860" rx="18" fill="#f8fafc"/>',
           '<rect x="0" y="0" width="640" height="140" rx="18" fill="#102b3f"/>',
           '<rect x="0" y="110" width="640" height="30" fill="#102b3f"/>',
           '<g font-family="DejaVu Sans, Arial, sans-serif" fill="#102b3f">']

    def text(x, y, content, size=18, color="#102b3f", weight="normal", anchor="start"):
        out.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}">{escape(str(content))}</text>')

    text(28, 35, f"SEARCH LAB  /  {report['product_count']} SYNTHETIC PRODUCTS", 15, "#b4e6e3", "bold")
    text(28, 76, "Same ranks. Useful failure cases.", 27, "#ffffff", "bold")
    text(28, 111, "TF-IDF and BM25 · held-out evaluation", 19, "#dce9f0")
    text(28, 179, "Where the first relevant product appears", 21, weight="bold")
    text(28, 209, f"{n} answerable queries · both methods have these counts", 17, "#43556b")
    x0, max_width, max_count = 146, 390, n
    for j, rank in enumerate([*range(1, k + 1), 0]):
        y = 243 + j * 43
        count = counts[rank]
        label = f"Rank {rank}" if rank else f"Not in top {k}"
        color = "#087f81" if rank == 1 else "#ad4b20"
        text(28, y + 20, label, 18)
        out.append(f'<rect x="{x0}" y="{y}" width="{max_width}" height="27" rx="5" fill="#e7edf3"/>')
        if count:
            out.append(f'<rect x="{x0}" y="{y}" width="{max_width * count / max_count:.4f}" height="27" rx="5" fill="{color}"/>')
        text(610, y + 20, f"{count}/{n}", 19, weight="bold", anchor="end")
    text(28, 526, f"MRR@{k}  {mrr:.4f}", 20, weight="bold")
    text(285, 526, f"Recall@{k}  {recall:.4f}", 20, weight="bold")
    text(28, 555, "Lower-order rankings can still differ between methods.", 17, "#43556b")

    for idx, row in enumerate(failures):
        y = 581 + idx * 100
        relevant = catalog[row["relevant_ids"][0]]["title"]
        top = catalog[row["top_ids"][0]]["title"]
        rank = round(1 / row["reciprocal_rank_at_k"])
        out.append(f'<rect x="22" y="{y}" width="596" height="88" rx="9" fill="#fff2e7" stroke="#e7c5aa"/>')
        text(36, y + 25, f"{row['id']}  {row['query']}", 17, weight="bold")
        text(36, y + 51, f"#{1}  {top}", 16, "#89401e")
        text(36, y + 74, f"#{rank}  {relevant}  [relevant]", 16, "#102b3f")

    rejected = sum(not r["false_positive_no_answer"] for r in no_answer)
    text(28, 800, f"No-answer check: {rejected}/{len(no_answer)} returned no results (reported separately).", 15, "#43556b")
    text(28, 827, "Tiny author-labelled demo. No independent or production claim.", 15, "#43556b")
    out.extend(['</g>', '</svg>', ''])
    return "\n".join(out)


def artifacts():
    report = checked_report()
    inputs = ["catalog_search/evaluate.py", "catalog_search/engine.py", "data/catalog.json", "data/queries.json",
              "results/evaluation.json", "results/per-query.csv", "scripts/render_readme_visual.py"]
    provenance = {"schema_version": 1, "figure": "heldout-ranking.svg", "renderer": "Python standard library; no external assets",
                  "scope": f"{report['splits']['heldout']['answerable_queries']} answerable held-out synthetic author-labelled queries; no-answer query reported separately",
                  "source_sha256": {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in inputs}}
    return {"heldout-ranking.svg": figure(report),
            "heldout-ranking.provenance.json": json.dumps(provenance, indent=2) + "\n"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = artifacts()
    if args.check:
        for name, content in files.items():
            if not (DEST / name).is_file() or (DEST / name).read_text(encoding="utf-8") != content:
                raise SystemExit(f"Stale visual: {DEST / name}. Regenerate and inspect before committing.")
        print("README visual and provenance match exact recomputation.")
    else:
        DEST.mkdir(parents=True, exist_ok=True)
        for name, content in files.items():
            (DEST / name).write_text(content, encoding="utf-8", newline="\n")
        print("Generated README visual and provenance from checked evaluation.")


if __name__ == "__main__":
    main()
