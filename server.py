import argparse
import base64
import binascii
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from core import APP, models
from feature import handle, initialize, PORT


class Handler(BaseHTTPRequestHandler):
    def output(self, value, code=200, kind="application/json"):
        raw = json.dumps(value).encode() if kind == "application/json" else value
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; object-src 'none'; frame-ancestors 'none'")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def route(self, post=False):
        allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        if host not in allowed or (origin and origin != "http://" + host):
            return self.output({"error": "This app accepts requests from its local page only."}, 403)
        path = urlsplit(self.path).path
        if not post and path in {"/", "/style.css", "/ui.js"}:
            filename, kind = {"/": ("app.html", "text/html"), "/style.css": ("style.css", "text/css"),
                              "/ui.js": ("ui.js", "application/javascript")}[path]
            return self.output((APP / filename).read_bytes(), kind=kind + "; charset=utf-8")
        if not path.startswith("/api/"):
            return self.output({"error": "Unknown route."}, 404)
        payload = {}
        try:
            if post:
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    return self.output({"error": "Expected JSON."}, 415)
                size = int(self.headers.get("Content-Length", 0))
                if not 0 < size <= 42_000_000:
                    return self.output({"error": "Invalid request size."}, 413)
                payload = json.loads(self.rfile.read(size))
            action = path[5:]
            if not post and action == "models":
                try:
                    return self.output(models())
                except OSError:
                    return self.output({"chat": [], "embedding": [], "offline": True})
            response = handle(action, payload, post)
            if hasattr(response, "__next__"):
                first = next(response, None)
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                try:
                    if first is not None:
                        self.chunk(first)
                    for item in response:
                        self.chunk(item)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                except Exception as error:
                    self.chunk({"error": str(error)})
                finally:
                    response.close()
                return
            return self.output(response)
        except (BrokenPipeError, ConnectionResetError):
            return
        except (ValueError, KeyError, TypeError, OSError, binascii.Error) as error:
            return self.output({"error": str(error)}, 400)
        except Exception as error:
            self.log_error("%r", error)
            return self.output({"error": "Request failed. Check the local server log."}, 500)

    def chunk(self, item):
        self.wfile.write((json.dumps(item) + "\n").encode())
        self.wfile.flush()

    def do_GET(self):
        self.route()

    def do_POST(self):
        self.route(post=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    initialize()
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
        print(f"Open http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
