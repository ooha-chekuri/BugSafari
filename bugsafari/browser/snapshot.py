"""Extract one immutable :class:`Snapshot` from the live page.

This is the only place that understands the demo's DOM conventions
(``data-product``, ``quantity-*``, ``line-total-*``). Rules stay pure.
"""

from __future__ import annotations

from collections.abc import Sequence

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from bugsafari.money import parse_money
from bugsafari.reporting.models import CatalogItem, Snapshot

PRICE_ATTRIBUTE = "data-price"
PRODUCT_ATTRIBUTE = "data-product"
QUANTITY_PREFIX = "quantity-"
LINE_TOTAL_PREFIX = "line-total-"


class SnapshotError(RuntimeError):
    """The page did not expose the observations the rules need."""


def capture_snapshot(page: Page, capture: Sequence[str] = ()) -> Snapshot:
    """Read the catalog, cart, and requested test-id texts from ``page``."""
    catalog = _capture_catalog(page)
    cart, line_totals, row_count = _capture_cart(page)
    texts: dict[str, str] = {}
    for test_id in capture:
        try:
            texts[test_id] = page.get_by_test_id(test_id).inner_text().strip()
        except PlaywrightTimeoutError as exc:
            raise SnapshotError(f"could not read {test_id!r}: element not visible") from exc
    return Snapshot(
        url=page.url,
        catalog=catalog,
        cart=cart,
        texts=texts,
        line_totals=line_totals,
        row_count=row_count,
    )


def _capture_catalog(page: Page) -> dict[str, CatalogItem]:
    catalog: dict[str, CatalogItem] = {}
    for element in page.locator(f"[{PRODUCT_ATTRIBUTE}]").all():
        product_id = element.get_attribute(PRODUCT_ATTRIBUTE)
        if not product_id:
            continue
        price_text = element.get_attribute(PRICE_ATTRIBUTE) or ""
        price_cents = parse_money(price_text)
        if price_cents is None:
            raise SnapshotError(
                f"product {product_id!r} has an unreadable price: {price_text!r}"
            )
        name = (element.locator("strong").first.inner_text() or product_id).strip()
        catalog[product_id] = CatalogItem(
            id=product_id, name=name, price_cents=price_cents
        )
    return catalog


def _capture_cart(page: Page) -> tuple[dict[str, int], dict[str, str], int]:
    cart: dict[str, int] = {}
    line_totals: dict[str, str] = {}
    for element in page.locator('input[data-testid^="quantity-"]').all():
        test_id = element.get_attribute("data-testid") or ""
        product_id = test_id[len(QUANTITY_PREFIX):]
        if not product_id:
            continue
        raw_quantity = element.input_value()
        try:
            cart[product_id] = int(raw_quantity)
        except ValueError as exc:
            raise SnapshotError(
                f"quantity for {product_id!r} is not a number: {raw_quantity!r}"
            ) from exc
        line = page.get_by_test_id(f"{LINE_TOTAL_PREFIX}{product_id}")
        if line.count() == 0:
            raise SnapshotError(f"line total for {product_id!r} is missing")
        line_totals[product_id] = line.inner_text().strip()
    return cart, line_totals, len(cart)
