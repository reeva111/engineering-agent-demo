"""HTTP transport and application configuration for the quote service."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from quote_service.shipping import calculate_quote


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "quote.json"
MAX_REQUEST_BYTES = 4096


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> ThreadingHTTPServer:
    with config_path.open(encoding="utf-8") as config_file:
        config = json.load(config_file)

    class QuoteRequestHandler(BaseHTTPRequestHandler):
        def _send_json(self, status: int, payload: dict[str, int | str]) -> None:
            body = json.dumps(payload, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path == "/healthz":
                self._send_json(200, {"status": "ok"})
                return
            self._send_json(404, {"error": "not_found"})

        def do_POST(self) -> None:
            if self.path != "/quote":
                self._send_json(404, {"error": "not_found"})
                return

            try:
                content_length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send_json(400, {"error": "invalid_content_length"})
                return
            if not 0 <= content_length <= MAX_REQUEST_BYTES:
                self._send_json(400, {"error": "invalid_content_length"})
                return

            try:
                payload = json.loads(self.rfile.read(content_length))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._send_json(400, {"error": "invalid_json"})
                return

            if not isinstance(payload, dict) or set(payload) != {"subtotal_cents"}:
                self._send_json(400, {"error": "invalid_request_shape"})
                return

            subtotal_cents = payload["subtotal_cents"]
            if type(subtotal_cents) is not int or subtotal_cents < 0:
                self._send_json(400, {"error": "invalid_subtotal_cents"})
                return

            quote = calculate_quote(subtotal_cents, **config)
            self._send_json(200, quote)

        def log_message(self, format: str, *args: object) -> None:
            # Tests and the command-line entry point provide their own output.
            return

    return ThreadingHTTPServer((host, port), QuoteRequestHandler)
