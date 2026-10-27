import math
import unittest

from catalog_search.engine import SearchError, SearchIndex, tokenize
from catalog_search.evaluate import metrics_for


def product(pid, title, category="Office", price=1000, description=""):
    return {"id": pid, "title": title, "category": category, "price_cents": price,
            "description": description, "tags": []}


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.index = SearchIndex([product("p1", "Red desk lamp", price=2000),
                                  product("p2", "Blue desk lamp", price=3000),
                                  product("p3", "Red water bottle", "Outdoors", 1500)])

    def test_known_scores_match_hand_calculation(self):
        for method in ("tfidf", "bm25"):
            result = self.index.search("desk", method)["results"][0]
            self.assertEqual(result["id"], "p1")
            if method == "tfidf":
                # p1 has four equally weighted terms, so one term is 1/sqrt(4).
                expected = 0.5
            else:
                # All documents have four tokens, so length normalization is 1.
                expected = math.log(1 + 1.5 / 2.5)
            self.assertAlmostEqual(result["score"], expected)

    def test_explanations_sum_to_score_and_only_match_terms(self):
        for method in ("tfidf", "bm25"):
            for result in self.index.search("red desk", method)["results"]:
                self.assertAlmostEqual(result["score"], sum(x["contribution"] for x in result["explanation"]))
                self.assertTrue(set(result["matched_terms"]) <= {"red", "desk"})

    def test_filters_are_inclusive_and_consistent_across_methods(self):
        filters = self.index.filters("Office", "20", "20.00")
        for method in ("tfidf", "bm25"):
            self.assertEqual([r["id"] for r in self.index.search("lamp", method, filters)["results"]], ["p1"])
            self.assertEqual([r["id"] for r in self.index.search("", method, filters)["results"]], ["p1"])

    def test_no_matching_terms_and_stop_words_return_empty(self):
        for query in ("zxquv", "the and", "!!!", "机"):
            for method in ("tfidf", "bm25"):
                self.assertEqual(self.index.search(query, method)["results"], [])

    def test_blank_query_browses_without_relevance_score(self):
        response = self.index.search("   ", limit=2)
        self.assertEqual(response["total"], 3)
        self.assertEqual([r["id"] for r in response["results"]], ["p1", "p2"])
        self.assertIsNone(response["results"][0]["score"])

    def test_bad_queries_methods_and_limits(self):
        for query in (None, 42, [], "x" * 257, "a\x00b", "desk\nred", " ".join(["desk"] * 33)):
            with self.subTest(query=query), self.assertRaises(SearchError):
                self.index.search(query)
        for limit in (-1, 0, 51, True, 1.2, "2"):
            with self.subTest(limit=limit), self.assertRaises(SearchError):
                self.index.search("lamp", limit=limit)
        with self.assertRaisesRegex(SearchError, "not implemented"):
            self.index.search("lamp", method="semantic")

    def test_invalid_prices_categories_and_range(self):
        for price in ("NaN", "Infinity", "-1", "1.001", "abc", "1000001", True,
                      "1.00000000000000000000000000001", "10.00000000000000000000000000001",
                      "1e-999999999", "1e2"):
            with self.subTest(price=price), self.assertRaises(SearchError):
                self.index.filters(min_price=price)
        with self.assertRaises(SearchError):
            self.index.filters(min_price="30", max_price="20")
        with self.assertRaises(SearchError):
            self.index.filters(category="Missing")
        self.assertEqual(self.index.filters(min_price=".50").min_price_cents, 50)

    def test_unicode_normalization_and_no_query_execution(self):
        self.assertEqual(tokenize("ＤＥＳＫ Lamp"), ["desk", "lamp"])
        response = self.index.search("<script>alert(1)</script> OR 1=1")
        self.assertEqual(response["results"], [])

    def test_rank_ties_are_stable_and_no_duplicate_results(self):
        for method in ("tfidf", "bm25"):
            ids = [r["id"] for r in self.index.search("lamp lamp", method)["results"]]
            self.assertEqual(ids, ["p1", "p2"])
            self.assertEqual(len(ids), len(set(ids)))

    def test_empty_filter_intersection(self):
        response = self.index.search("lamp", filters=self.index.filters("Outdoors", "50"))
        self.assertEqual(response["total"], 0)


class MetricTests(unittest.TestCase):
    def test_reciprocal_rank_and_recall_at_cutoff(self):
        self.assertEqual(metrics_for(["a", "b", "c", "d"], ["b", "d"], k=3), (0.5, 0.5))
        self.assertEqual(metrics_for(["a", "b"], ["c"]), (0.0, 0.0))
        self.assertEqual(metrics_for([], []), (None, None))
        self.assertEqual(metrics_for(["b", "b"], ["b", "c"]), (1.0, 0.5))


if __name__ == "__main__":
    unittest.main()
