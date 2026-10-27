from concurrent.futures import ThreadPoolExecutor
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen
from http.server import ThreadingHTTPServer

from catalog_search.engine import SearchIndex
from catalog_search.server import make_handler


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = SearchIndex.load()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cls.index))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def get(self, path):
        return urlopen(self.base + path, timeout=5)

    def test_static_and_meta(self):
        for path in ("/", "/app.js", "/styles.css"):
            with self.get(path) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
                self.assertIn("script-src 'self'", response.headers["Content-Security-Policy"])
                self.assertTrue(response.read())
        with self.get("/api/meta") as response:
            meta = json.load(response)
        self.assertEqual(meta["product_count"], self.index.size)
        self.assertFalse(meta["semantic"]["implemented"])

    def test_invalid_parameters_return_json_400(self):
        for suffix in ("q=a&q=b", "q=%00", "limit=abc", "limit=0", "min_price=NaN",
                       "min_price=1.00000000000000000000000000001", "max_price=1e-999999999",
                       "min_price=40&max_price=2", "category=invalid", "method=semantic", "foo=bar"):
            with self.subTest(suffix=suffix):
                with self.assertRaises(HTTPError) as caught:
                    self.get("/api/search?" + suffix)
                with caught.exception as response:
                    self.assertEqual(response.code, 400)
                    self.assertTrue(json.load(response)["error"])

    def test_api_matches_engine_and_concurrent_reads(self):
        def search(method):
            with self.get(f"/api/search?q=lamp&method={method}&max_price=100&limit=5") as response:
                actual = json.load(response)
            expected = self.index.search("lamp", method, self.index.filters(max_price="100"), 5)
            self.assertEqual(actual, expected)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(search, ["tfidf", "bm25"] * 4))

    def test_traversal_and_missing_paths_return_404(self):
        for path in ("/../data/catalog.json", "/data/catalog.json", "/.git/config", "/missing"):
            with self.subTest(path=path):
                with self.assertRaises(HTTPError) as caught:
                    self.get(path)
                with caught.exception as response:
                    self.assertEqual(response.code, 404)


if __name__ == "__main__":
    unittest.main()
