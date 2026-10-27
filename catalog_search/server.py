"""Local HTTP demo. Bind to loopback by default; no production hosting claim."""

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from urllib.parse import parse_qs, urlsplit

from .engine import METHODS, ROOT, SearchError, SearchIndex

STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/styles.css": ("styles.css", "text/css; charset=utf-8")}


def make_handler(index):
    class Handler(BaseHTTPRequestHandler):
        def send_bytes(self, status, content, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(content)

        def send_json(self, status, value):
            self.send_bytes(status, json.dumps(value, allow_nan=False).encode(), "application/json; charset=utf-8")

        def do_GET(self):
            try:
                path = urlsplit(self.path).path
                if path == "/api/meta":
                    report_path = ROOT / "results" / "evaluation.json"
                    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else None
                    self.send_json(200, {"product_count": index.size, "categories": index.categories,
                                         "methods": [{"id": key, "name": name, "description": "Lexical retrieval"}
                                                     for key, name in METHODS.items()],
                                         "semantic": {"implemented": False,
                                                      "reason": "No dense model runtime is bundled; no model is downloaded."},
                                         "evaluation": report})
                elif path == "/api/search":
                    if len(self.path) > 4096:
                        raise SearchError("Request URL is too long.")
                    params = parse_qs(urlsplit(self.path).query, keep_blank_values=True, max_num_fields=12)
                    allowed = {"q", "method", "category", "min_price", "max_price", "limit"}
                    if set(params) - allowed or any(len(values) != 1 for values in params.values()):
                        raise SearchError("Unknown or repeated search parameter.")
                    params = {key: values[0] for key, values in params.items()}
                    try:
                        limit = int(params.get("limit", "8"))
                    except ValueError:
                        raise SearchError("Limit must be an integer from 1 to 50.") from None
                    filters = index.filters(params.get("category"), params.get("min_price"), params.get("max_price"))
                    result = index.search(params.get("q", ""), params.get("method", "tfidf"), filters, limit)
                    self.send_json(200, result)
                elif path in STATIC:
                    filename, content_type = STATIC[path]
                    self.send_bytes(200, (ROOT / "static" / filename).read_bytes(), content_type)
                else:
                    self.send_json(404, {"error": "Not found."})
            except (SearchError, ValueError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(SearchIndex.load()))
    print(f"Synthetic Product Catalog Search: http://{args.host}:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
