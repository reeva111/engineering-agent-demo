# Engineering Agent Demo

A small shipping-quote service used by the Engineering Agent Platform's CI repair benchmark. It uses only the Python standard library.

The benchmark interpreter is Python 3.12.14. The source supports Python 3.12 and 3.13. Run the commands below from this directory with `python` pointing to the chosen interpreter.

## Run the service

```sh
python -B scripts/serve.py --host 127.0.0.1 --port 8000
```

`GET /healthz` returns HTTP 200 and `{"status": "ok"}`.

`POST /quote` accepts a JSON object containing only `subtotal_cents`. The value must be a nonnegative integer. Boolean values are rejected.

```json
{"subtotal_cents": 1234}
```

The response contains exactly four fields.

```json
{
  "subtotal_cents": 1234,
  "shipping_cents": 499,
  "total_cents": 1733,
  "currency": "USD"
}
```

Configuration is loaded from `config/quote.json` when the server starts. Shipping costs 499 cents for subtotals below 5000 cents. Subtotals of 5000 cents and above qualify for free shipping. A zero subtotal is valid and retains the 499-cent shipping charge.

Malformed JSON, invalid request shapes, and invalid subtotals return HTTP 400 with an `error` field. Unknown routes return HTTP 404.

## Run the tests

```sh
python -B -m unittest discover -s tests -t . -v
```

The tests start the normal HTTP server on a port allocated by the operating system. They exercise the HTTP API, apply request timeouts, and stop the server after the suite completes. They use the application configuration without replacing it in the test harness.

The `-t .` argument preserves test identifiers under the `tests.test_api` module. Tests require permission to connect to the loopback HTTP server. They use no external services or package downloads.
