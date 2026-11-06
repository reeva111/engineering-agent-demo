"""Calculate a quote using the application's shipping configuration."""


def calculate_quote(
    subtotal_cents: int,
    *,
    free_shipping_threshold_cents: int,
    shipping_cents: int,
    currency: str,
) -> dict[str, int | str]:
    shipping_cost = 0 if subtotal_cents >= free_shipping_threshold_cents else shipping_cents
    return {
        "subtotal_cents": subtotal_cents,
        "shipping_cents": shipping_cost,
        "total_cents": subtotal_cents + shipping_cost,
        "currency": currency,
    }
