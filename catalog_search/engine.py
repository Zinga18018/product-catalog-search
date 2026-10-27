"""TF-IDF cosine and BM25 retrieval, implemented with the standard library."""

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import math
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parent.parent
METHODS = {
    "tfidf": "TF-IDF cosine",
    "bm25": "BM25",
}
STOP_WORDS = frozenset("a an and are as at be by for from i in is it me my of on or that the this to with".split())
MAX_QUERY_LENGTH = 256


class SearchError(ValueError):
    """An invalid search request that is safe to display to the caller."""


def tokenize(text):
    """Unicode words, case folded; no stemming, typo repair, or synonyms."""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return [word for word in re.findall(r"[^\W_]+", normalized) if word not in STOP_WORDS]


def price_to_cents(value, name):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise SearchError(f"{name} must be a nonnegative price with at most two decimals.")
    try:
        raw = str(value).strip()
        # Validate the exact representation before Decimal arithmetic can round it.
        # Currency inputs deliberately exclude exponent notation and excessive digits.
        if len(raw) > 16 or not re.fullmatch(r"(?:[0-9]+(?:\.[0-9]{1,2})?|\.[0-9]{1,2})", raw):
            raise InvalidOperation
        amount = Decimal(raw)
        if not amount.is_finite() or amount < 0 or amount > Decimal("1000000"):
            raise InvalidOperation
        cents = amount * 100
        return int(cents)
    except (InvalidOperation, ValueError):
        raise SearchError(f"{name} must be a nonnegative price with at most two decimals.") from None


@dataclass(frozen=True)
class Filters:
    category: str | None = None
    min_price_cents: int | None = None
    max_price_cents: int | None = None

    def matches(self, product):
        return (
            (self.category is None or product["category"] == self.category)
            and (self.min_price_cents is None or product["price_cents"] >= self.min_price_cents)
            and (self.max_price_cents is None or product["price_cents"] <= self.max_price_cents)
        )


class SearchIndex:
    def __init__(self, products):
        self.products = sorted(products, key=lambda p: p["id"])
        if not self.products:
            raise ValueError("Catalog must contain products.")
        self.categories = sorted({p["category"] for p in self.products})
        self.by_id = {p["id"]: p for p in self.products}
        if len(self.by_id) != len(self.products):
            raise ValueError("Catalog IDs must be unique.")
        self.counts = {}
        for product in self.products:
            if not isinstance(product["price_cents"], int) or product["price_cents"] < 0:
                raise ValueError("Catalog prices must be nonnegative integer cents.")
            text = " ".join([product["title"], product["category"], product["description"], *product["tags"]])
            self.counts[product["id"]] = Counter(tokenize(text))
        self.document_frequency = Counter()
        for counts in self.counts.values():
            self.document_frequency.update(counts.keys())
        self.size = len(self.products)
        self.average_length = sum(map(lambda c: sum(c.values()), self.counts.values())) / self.size
        self.tfidf_idf = {term: math.log((1 + self.size) / (1 + df)) + 1
                          for term, df in self.document_frequency.items()}
        self.norms = {pid: math.sqrt(sum(((1 + math.log(tf)) * self.tfidf_idf[t]) ** 2
                                        for t, tf in counts.items()))
                      for pid, counts in self.counts.items()}

    @classmethod
    def load(cls, path=ROOT / "data" / "catalog.json"):
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def filters(self, category=None, min_price=None, max_price=None):
        if category == "":
            category = None
        if category is not None and category not in self.categories:
            raise SearchError("Unknown category.")
        low = price_to_cents(min_price, "Minimum price")
        high = price_to_cents(max_price, "Maximum price")
        if low is not None and high is not None and low > high:
            raise SearchError("Minimum price must not exceed maximum price.")
        return Filters(category, low, high)

    def search(self, query="", method="tfidf", filters=None, limit=8):
        if not isinstance(query, str):
            raise SearchError("Query must be text.")
        if len(query) > MAX_QUERY_LENGTH:
            raise SearchError(f"Query must be at most {MAX_QUERY_LENGTH} characters.")
        if any(unicodedata.category(char) == "Cc" for char in query):
            raise SearchError("Query must not contain control characters.")
        if method not in METHODS:
            raise SearchError("Choose tfidf or bm25. Dense semantic retrieval is not implemented.")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
            raise SearchError("Limit must be an integer from 1 to 50.")
        query = query.strip()
        terms = Counter(tokenize(query))
        if sum(terms.values()) > 32:
            raise SearchError("Query must contain at most 32 searchable words.")
        filters = filters or Filters()
        query_weights = {t: (1 + math.log(tf)) * self.tfidf_idf[t]
                         for t, tf in terms.items() if t in self.tfidf_idf}
        query_norm = math.sqrt(sum(weight ** 2 for weight in query_weights.values()))
        results = []
        for product in self.products:
            if not filters.matches(product):
                continue
            counts = self.counts[product["id"]]
            contributions = []
            for term in sorted(terms):
                frequency = counts[term]
                if not frequency:
                    continue
                if method == "tfidf":
                    denominator = query_norm * self.norms[product["id"]]
                    weight = query_weights[term] * (1 + math.log(frequency)) * self.tfidf_idf[term]
                    contribution = weight / denominator if denominator else 0
                else:
                    # Robertson-style positive IDF; binary query term weighting.
                    df = self.document_frequency[term]
                    idf = math.log(1 + (self.size - df + 0.5) / (df + 0.5))
                    length = sum(counts.values())
                    k1, b = 1.2, 0.75
                    contribution = idf * frequency * (k1 + 1) / (
                        frequency + k1 * (1 - b + b * length / self.average_length))
                contributions.append({"term": term, "contribution": contribution})
            score = sum(item["contribution"] for item in contributions)
            if query and score <= 0:
                continue
            results.append({**product, "score": score if query else None,
                            "matched_terms": [item["term"] for item in contributions],
                            "explanation": contributions})
        results.sort(key=lambda p: (-(p["score"] or 0), p["id"]))
        return {"query": query, "method": method, "total": len(results), "results": results[:limit],
                "filters": {"category": filters.category,
                            "min_price_cents": filters.min_price_cents,
                            "max_price_cents": filters.max_price_cents}}
