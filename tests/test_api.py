"""Exercise the service over HTTP with an operating-system-assigned port."""

import json
from pathlib import Path
import sys
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from quote_service.server import create_server


class QuoteAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = create_server("127.0.0.1", 0)
        cls.server_thread = threading.Thread(
            target=cls.server.serve_forever,
            kwargs={"poll_interval": 0.01},
            name="quote-api-test-server",
            daemon=True,
        )
        cls.server_thread.start()
        cls.addClassCleanup(cls.stop_server)
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def stop_server(cls) -> None:
        try:
            cls.server.shutdown()
        finally:
            cls.server.server_close()
            cls.server_thread.join(timeout=2)
        if cls.server_thread.is_alive():
            raise RuntimeError("The HTTP test server did not stop.")

    def request_json(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
    ) -> tuple[int, dict[str, object]]:
        request = Request(
            self.base_url + path,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            response = urlopen(request, timeout=3)
        except HTTPError as error:
            response = error
        with response:
            self.assertEqual(response.headers.get_content_type(), "application/json")
            payload = json.load(response)
            self.assertIsInstance(payload, dict)
            return response.status, payload

    def quote(self, subtotal_cents: int) -> dict[str, object]:
        body = json.dumps({"subtotal_cents": subtotal_cents}).encode("utf-8")
        status, payload = self.request_json("POST", "/quote", body)
        self.assertEqual(status, 200)
        return payload

    def test_healthz(self) -> None:
        status, payload = self.request_json("GET", "/healthz")
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"status": "ok"})

    def test_quote_response_contract(self) -> None:
        for subtotal, shipping in ((1234, 499), (4999, 499), (5000, 0), (5001, 0), (0, 499)):
            payload = self.quote(subtotal)
            self.assertEqual(
                set(payload),
                {"subtotal_cents", "shipping_cents", "total_cents", "currency"},
                "The quote response must retain its published field names.",
            )
            for field in ("subtotal_cents", "shipping_cents", "total_cents"):
                self.assertIs(type(payload[field]), int)
            self.assertIsInstance(payload["currency"], str)
            self.assertEqual(payload["subtotal_cents"], subtotal)
            self.assertEqual(payload["shipping_cents"], shipping)
            self.assertEqual(payload["total_cents"], subtotal + shipping)

    def test_shipping_below_threshold(self) -> None:
        payload = self.quote(4999)
        self.assertIn("shipping_cents", payload)
        self.assertEqual(payload["shipping_cents"], 499)

    def test_free_shipping_at_threshold(self) -> None:
        payload = self.quote(5000)
        self.assertIn("shipping_cents", payload)
        self.assertEqual(
            payload["shipping_cents"],
            0,
            "The free-shipping threshold includes a subtotal of 5000 cents.",
        )

    def test_free_shipping_above_threshold(self) -> None:
        payload = self.quote(5001)
        self.assertIn("shipping_cents", payload)
        self.assertEqual(payload["shipping_cents"], 0)

    def test_zero_subtotal(self) -> None:
        payload = self.quote(0)
        self.assertIn("subtotal_cents", payload)
        self.assertIn("shipping_cents", payload)
        self.assertEqual(payload["subtotal_cents"], 0)
        self.assertEqual(payload["shipping_cents"], 499)

    def test_currency_from_application_config(self) -> None:
        payload = self.quote(1234)
        self.assertIn("currency", payload)
        self.assertEqual(
            payload["currency"],
            "USD",
            "Quotes must use the application's configured USD currency.",
        )

    def test_invalid_json(self) -> None:
        status, payload = self.request_json("POST", "/quote", b"{broken json")
        self.assertEqual(status, 400)
        self.assertEqual(payload, {"error": "invalid_json"})

    def test_negative_subtotal(self) -> None:
        status, payload = self.request_json("POST", "/quote", b'{"subtotal_cents": -1}')
        self.assertEqual(status, 400)
        self.assertEqual(payload, {"error": "invalid_subtotal_cents"})

    def test_boolean_subtotal(self) -> None:
        for value in (True, False):
            with self.subTest(value=value):
                body = json.dumps({"subtotal_cents": value}).encode("utf-8")
                status, payload = self.request_json("POST", "/quote", body)
                self.assertEqual(status, 400)
                self.assertEqual(payload, {"error": "invalid_subtotal_cents"})

    def test_non_integer_subtotal(self) -> None:
        for value in (1.5, "5000", None):
            with self.subTest(value=value):
                body = json.dumps({"subtotal_cents": value}).encode("utf-8")
                status, payload = self.request_json("POST", "/quote", body)
                self.assertEqual(status, 400)
                self.assertEqual(payload, {"error": "invalid_subtotal_cents"})

    def test_invalid_request_shape(self) -> None:
        for value in (None, [], 42, {}, {"subtotal_cents": 1, "extra": True}):
            with self.subTest(value=value):
                body = json.dumps(value).encode("utf-8")
                status, payload = self.request_json("POST", "/quote", body)
                self.assertEqual(status, 400)
                self.assertEqual(payload, {"error": "invalid_request_shape"})

    def test_unknown_route(self) -> None:
        for method in ("GET", "POST"):
            with self.subTest(method=method):
                status, payload = self.request_json(method, "/missing")
                self.assertEqual(status, 404)
                self.assertEqual(payload, {"error": "not_found"})


if __name__ == "__main__":
    unittest.main()
