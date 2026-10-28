"""Extract one immutable :class:`Snapshot` from the live page.

This is the only place that understands the demo's DOM conventions
(``data-product``, ``quantity-*``, ``line-total-*``). Rules stay pure.
"""

from __future__ import annotations

from collections.abc import Sequence

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from bugsafari.money import parse_money
from bugsafari.reporting.models import CatalogItem, ElementObservation, Snapshot

PRICE_ATTRIBUTE = "data-price"
PRODUCT_ATTRIBUTE = "data-product"
QUANTITY_PREFIX = "quantity-"
LINE_TOTAL_PREFIX = "line-total-"


class SnapshotError(RuntimeError):
    """The page did not expose the observations the rules need."""


def capture_snapshot(
    page: Page,
    capture: Sequence[str] = (),
    *,
    include_shop_data: bool = True,
) -> Snapshot:
    """Read requested page observations and optional bundled-shop facts."""
    catalog = _capture_catalog(page) if include_shop_data else {}
    if include_shop_data:
        cart, line_totals, row_count = _capture_cart(page)
    else:
        cart, line_totals, row_count = {}, {}, 0
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
        elements=_capture_elements(page),
        viewport=page.evaluate("({width: innerWidth, height: innerHeight})"),
        document_width=page.evaluate("document.documentElement.scrollWidth"),
    )


def _capture_elements(page: Page) -> tuple[ElementObservation, ...]:
    """Capture visible text, controls, and images for deterministic checkers."""
    records = page.locator("body *").evaluate_all(
        r"""elements => {
          const selectorFor = element => {
            if (element.id) return `#${CSS.escape(element.id)}`;
            const testId = element.getAttribute('data-testid');
            if (testId) return `[data-testid="${CSS.escape(testId)}"]`;
            const parts = [];
            for (let node = element; node && node !== document.body; node = node.parentElement) {
              if (node.id) {
                parts.unshift(`#${CSS.escape(node.id)}`);
                break;
              }
              const nodeTestId = node.getAttribute('data-testid');
              if (nodeTestId) {
                parts.unshift(`[data-testid="${CSS.escape(nodeTestId)}"]`);
                break;
              }
              let part = node.tagName.toLowerCase();
              if (node.parentElement) {
                const siblings = [...node.parentElement.children].filter(sibling =>
                  sibling.tagName === node.tagName
                );
                if (siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
              }
              parts.unshift(part);
            }
            return parts.join(' > ');
          };
          const isControl = e =>
            /^(BUTTON|A|INPUT|SELECT|TEXTAREA)$/.test(e.tagName) ||
            e.getAttribute('role') === 'button';
          const isImage = e => e.tagName === 'IMG';
          const hasText = e =>
            !!(e.innerText || '').trim() &&
            e.matches('p, span, small, strong, em, label, h1, h2, h3, h4, h5, h6, li');
          const result = [], likelyOverlays = [];
          for (const e of elements) {
            const style = getComputedStyle(e);
            const rect = e.getBoundingClientRect();
            const visible = style.display !== 'none' &&
              style.visibility !== 'hidden' && Number(style.opacity) !== 0 &&
              rect.width > 0 && rect.height > 0;
            if (!visible) continue;
            const zIndexValue = Number.parseInt(style.zIndex, 10);
            const zIndex = Number.isFinite(zIndexValue) ? zIndexValue : null;
            const viewportArea = Math.max(1, innerWidth * innerHeight);
            const visibleArea = Math.max(0, Math.min(rect.right, innerWidth) - Math.max(rect.left, 0)) *
              Math.max(0, Math.min(rect.bottom, innerHeight) - Math.max(rect.top, 0));
            const coverage = visibleArea / viewportArea;
            const overlayCandidate = style.position === 'fixed' && coverage >= 0.12 &&
              ((zIndex !== null && zIndex >= 10) || coverage >= 0.5);
            if (!isControl(e) && !isImage(e) && !hasText(e) && !overlayCandidate) continue;
            const parent = e.parentElement, parentRect = parent?.getBoundingClientRect();
            const parentStyle = parent ? getComputedStyle(parent) : null;
            const labelledBy = e.getAttribute('aria-labelledby');
            const labelledText = labelledBy
              ? labelledBy.split(/\s+/)
                  .map(id => document.getElementById(id)?.innerText || '')
                  .join(' ').trim()
              : '';
            const label = e.labels?.length
              ? [...e.labels].map(item => item.innerText).join(' ').trim()
              : '';
            const accessibleName = e.getAttribute('aria-label') || labelledText || label ||
              e.getAttribute('title') ||
              [...(e.querySelectorAll?.('img') || [])]
                .map(image => image.getAttribute('alt') || '').join(' ').trim() ||
              (isImage(e) ? e.getAttribute('alt') :
                (isControl(e) ? (e.innerText || e.value || '') : ''));
            let background = style.backgroundColor;
            for (
              let node = e.parentElement;
              node && background === 'rgba(0, 0, 0, 0)';
              node = node.parentElement
            ) background = getComputedStyle(node).backgroundColor;
            if (background === 'rgba(0, 0, 0, 0)') background = null;
            const observation = {
              selector: selectorFor(e),
              tag: e.tagName.toLowerCase(),
              text: (e.innerText || '').trim().slice(0, 300),
              visible, interactive: isControl(e),
              bbox: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
              parent_selector: parent ? selectorFor(parent) : null,
              parent_bbox: parentRect ? {
                x: parentRect.x, y: parentRect.y,
                width: parentRect.width, height: parentRect.height
              } : {},
              parent_clips: !!parentStyle && /(hidden|clip|auto|scroll)/.test(
                `${parentStyle.overflow} ${parentStyle.overflowX} ${parentStyle.overflowY}`
              ),
              font_size_px: parseFloat(style.fontSize), font_weight: style.fontWeight,
              color: style.color, background_color: background,
              position: style.position, z_index: zIndex,
              role: e.getAttribute('role') || (e.tagName === 'DIALOG' ? 'dialog' : null),
              aria_modal: e.getAttribute('aria-modal') === 'true',
              accessible_name: accessibleName || '',
              has_label: isControl(e) && /^(INPUT|SELECT|TEXTAREA)$/.test(e.tagName)
                ? !!(accessibleName || (e.type === 'hidden'))
                : null,
              image_loaded: isImage(e) ? (e.complete && e.naturalWidth > 0) : null,
              natural_width: isImage(e) ? e.naturalWidth : null,
              natural_height: isImage(e) ? e.naturalHeight : null,
              alt: isImage(e) ? e.getAttribute('alt') : null,
              decorative: isImage(e) && (
                e.getAttribute('role') === 'presentation' ||
                e.getAttribute('aria-hidden') === 'true' ||
                (e.getAttribute('alt') === '' && !e.closest('a'))
              ),
              object_fit: isImage(e) ? style.objectFit : 'fill'
            };
            if (overlayCandidate) likelyOverlays.push(observation);
            else result.push(observation);
          }
          return [...likelyOverlays.slice(0, 200), ...result.slice(0, 1000)];
        }"""
    )
    return tuple(ElementObservation.from_dict(record) for record in records)


def _capture_catalog(page: Page) -> dict[str, CatalogItem]:
    catalog: dict[str, CatalogItem] = {}
    for element in page.locator(f"[{PRODUCT_ATTRIBUTE}]").all():
        product_id = element.get_attribute(PRODUCT_ATTRIBUTE)
        if not product_id:
            continue
        price_text = element.get_attribute(PRICE_ATTRIBUTE) or ""
        price_cents = parse_money(price_text)
        if price_cents is None:
            raise SnapshotError(f"product {product_id!r} has an unreadable price: {price_text!r}")
        name = (element.locator("strong").first.inner_text() or product_id).strip()
        catalog[product_id] = CatalogItem(id=product_id, name=name, price_cents=price_cents)
    return catalog


def _capture_cart(page: Page) -> tuple[dict[str, int], dict[str, str], int]:
    cart: dict[str, int] = {}
    line_totals: dict[str, str] = {}
    for element in page.locator('input[data-testid^="quantity-"]').all():
        test_id = element.get_attribute("data-testid") or ""
        product_id = test_id[len(QUANTITY_PREFIX) :]
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
