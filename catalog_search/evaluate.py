"""Recompute the checked-in small synthetic benchmark without external services."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

from .engine import METHODS, ROOT, SearchIndex

K = 5


def metrics_for(ranked_ids, relevant_ids, k=K):
    """Return truncated reciprocal rank and recall; undefined on no-answer queries."""
    relevant = set(relevant_ids)
    if not relevant:
        return None, None
    top = ranked_ids[:k]
    reciprocal_rank = next((1 / rank for rank, pid in enumerate(top, 1) if pid in relevant), 0.0)
    recall = len(set(top) & relevant) / len(relevant)
    return reciprocal_rank, recall


def evaluate(catalog_path=ROOT / "data" / "catalog.json", queries_path=ROOT / "data" / "queries.json"):
    index = SearchIndex.load(catalog_path)
    queries = json.loads(Path(queries_path).read_text(encoding="utf-8"))
    ids = [case["id"] for case in queries]
    if len(ids) != len(set(ids)):
        raise ValueError("Query IDs must be unique.")
    rows = []
    for case in queries:
        if case["split"] not in {"dev", "heldout"}:
            raise ValueError("Query split must be dev or heldout.")
        relevant = case["relevant_ids"]
        if len(relevant) != len(set(relevant)) or set(relevant) - set(index.by_id):
            raise ValueError(f"Invalid relevant IDs in {case['id']}")
        filters = index.filters(**case.get("filters", {}))
        if any(not filters.matches(index.by_id[pid]) for pid in relevant):
            raise ValueError(f"Judgments conflict with filters in {case['id']}")
        for method in METHODS:
            results = index.search(case["query"], method, filters, limit=K)
            ranked = [product["id"] for product in results["results"]]
            reciprocal_rank, recall = metrics_for(ranked, relevant)
            rows.append({"id": case["id"], "split": case["split"], "query": case["query"],
                         "method": method, "relevant_ids": relevant, "top_ids": ranked,
                         "reciprocal_rank_at_k": reciprocal_rank, "recall_at_k": recall,
                         "false_positive_no_answer": bool(ranked) if not relevant else None})
    report = {"schema_version": 1, "k": K,
              "catalog_sha256": hashlib.sha256(Path(catalog_path).read_bytes()).hexdigest(),
              "queries_sha256": hashlib.sha256(Path(queries_path).read_bytes()).hexdigest(),
              "product_count": index.size,
              "notes": "Synthetic author-judged demo; no independent benchmark or production claim. "
                       "MRR@k and Recall@k average only answerable queries; no-answer false positives are separate.",
              "splits": {}, "per_query": rows}
    for split in ("dev", "heldout"):
        cases = [case for case in queries if case["split"] == split]
        summary = {"query_count": len(cases), "answerable_queries": sum(bool(c["relevant_ids"]) for c in cases),
                   "no_answer_queries": sum(not c["relevant_ids"] for c in cases)}
        if not summary["answerable_queries"]:
            raise ValueError(f"No answerable queries in {split}.")
        for method in METHODS:
            method_rows = [row for row in rows if row["split"] == split and row["method"] == method]
            answerable = [row for row in method_rows if row["relevant_ids"]]
            unanswerable = [row for row in method_rows if not row["relevant_ids"]]
            summary[method] = {
                "mrr_at_k": sum(r["reciprocal_rank_at_k"] for r in answerable) / len(answerable),
                "recall_at_k": sum(r["recall_at_k"] for r in answerable) / len(answerable),
                "no_answer_false_positive_rate": (sum(r["false_positive_no_answer"] for r in unanswerable)
                                                  / len(unanswerable)) if unanswerable else None}
        report["splits"][split] = summary
    return report


def render_csv(report):
    output = io.StringIO(newline="")
    fields = ["id", "split", "query", "method", "relevant_ids", "top_ids", "reciprocal_rank_at_k",
              "recall_at_k", "false_positive_no_answer"]
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in report["per_query"]:
        writer.writerow({**row, "relevant_ids": " ".join(row["relevant_ids"]),
                         "top_ids": " ".join(row["top_ids"])})
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if stored artifacts differ from recomputation")
    args = parser.parse_args()
    report = evaluate()
    artifacts = {"evaluation.json": json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                 "per-query.csv": render_csv(report)}
    destination = ROOT / "results"
    if args.check:
        for filename, content in artifacts.items():
            path = destination / filename
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                raise SystemExit(f"Stale artifact: {path}. Run python -m catalog_search.evaluate")
        print("Evaluation artifacts match recomputation.")
    else:
        destination.mkdir(exist_ok=True)
        for filename, content in artifacts.items():
            (destination / filename).write_text(content, encoding="utf-8", newline="\n")
    for split, summary in report["splits"].items():
        print(f"{split}: {summary['answerable_queries']} answerable / {summary['no_answer_queries']} no-answer queries")
        for method in METHODS:
            values = summary[method]
            print(f"  {method}: MRR@{K}={values['mrr_at_k']:.4f}, Recall@{K}={values['recall_at_k']:.4f}, "
                  f"no-answer false-positive rate={values['no_answer_false_positive_rate']}")


if __name__ == "__main__":
    main()
