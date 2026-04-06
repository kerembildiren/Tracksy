"""
Simple server for SportsGuesser web app.
Serves static files from web/ and allplayers.json at /api/allplayers.
Run from SportsGuesser folder: python server.py
"""
import json
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(ROOT, "web")
ALLPLAYERS_PATH = os.path.join(ROOT, "DataCollection", "basketball", "output", "allplayers.json")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_GET(self):
        if self.path == "/api/allplayers" or self.path == "/api/allplayers/":
            self.serve_allplayers()
            return
        super().do_GET()

    def serve_allplayers(self):
        try:
            with open(ALLPLAYERS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except FileNotFoundError:
            self.send_error(404, "allplayers.json not found")
        except Exception as e:
            self.send_error(500, str(e))


def main():
    port = 8080
    server = HTTPServer(("", port), Handler)
    print(f"Serving at http://localhost:{port}")
    print("Open http://localhost:8080 in your browser.")
    server.serve_forever()


if __name__ == "__main__":
    main()
