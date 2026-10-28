"""Loopback-only dashboard server. No third-party runtime needed."""

import csv
import io
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .config import RigConfig
from .service import LabService


def make_server(port=8765, service=None):
    service = service or LabService()
    static = Path(__file__).parent / "static"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def allowed(self):
            bound_port = self.server.server_port
            hosts = {f"127.0.0.1:{bound_port}", f"localhost:{bound_port}"}
            if self.headers.get("Host") not in hosts:
                return False
            origin = self.headers.get("Origin")
            return origin is None or origin in {f"http://{h}" for h in hosts}

        def send_bytes(self, body, content_type, status=200, filename=None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, payload, status=200, filename=None):
            self.send_bytes(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"),
                            "application/json; charset=utf-8", status, filename)

        def do_GET(self):
            if not self.allowed():
                return self.send_json({"error": "Loopback host/origin required"}, 403)
            path = urlsplit(self.path).path
            with service.lock:
                if path == "/api/state":
                    return self.send_json(service.public_state())
                if path == "/api/export.json":
                    return self.send_json(service.export(), filename="mixsim-run.json")
                if path == "/api/export.csv":
                    output = io.StringIO(newline="")
                    fields = ["id", "kind", "label", "started_s", "finished_s", "a_ul_min", "b_ul_min", "settle_s",
                              "error_rgb_dn", "pressure_kpa", "status", "interlock", "recommended_from"]
                    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
                    writer.writeheader()
                    for record in service.records:
                        row = record.copy()
                        if row["label"].startswith(("=", "+", "-", "@")):
                            row["label"] = "'" + row["label"]
                        writer.writerow(row)
                    return self.send_bytes(output.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8", filename="mixsim-records.csv")
            files = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}
            if path in files:
                file = static / files[path]
                return self.send_bytes(file.read_bytes(), (mimetypes.guess_type(str(file))[0] or "text/plain") + "; charset=utf-8")
            self.send_json({"error": "Not found"}, 404)

        def do_POST(self):
            if not self.allowed():
                return self.send_json({"error": "Loopback host/origin required"}, 403)
            if urlsplit(self.path).path != "/api/action":
                return self.send_json({"error": "Not found"}, 404)
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 32768:
                    return self.send_json({"error": "Request size must be 1..32768 bytes"}, 413)
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    return self.send_json({"error": "application/json required"}, 415)
                def reject_constant(value):
                    raise ValueError(f"Nonfinite JSON constant {value}")
                request = json.loads(self.rfile.read(size), parse_constant=reject_constant)
                if not isinstance(request, dict) or not isinstance(request.get("action"), str):
                    raise ValueError("Expected object with action string")
                params = request.get("params", {})
                if not isinstance(params, dict):
                    raise ValueError("params must be an object")
                source = request.get("source", "ui")
                if source not in ("ui", "cli", "mcp", "python", "baseline"):
                    raise ValueError("Unknown source")
                return self.send_json(service.dispatch(request["action"], params, source))
            except (ValueError, UnicodeError) as exc:
                self.send_json({"ok": False, "error": {"code": "invalid_request", "message": str(exc)}}, 400)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve(port=8765, config: RigConfig | None = None):
    server = make_server(port, LabService(config))
    print(f"MixSim dashboard: http://127.0.0.1:{server.server_port}", flush=True)
    print("Simulation only. Ctrl+C to stop. MCP clients share this session through the bridge.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
