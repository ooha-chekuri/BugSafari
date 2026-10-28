"""Conservative, deterministic P0 checks over captured DOM observations."""

from __future__ import annotations

import re
from collections.abc import Iterable

from bugsafari.reporting.models import ElementObservation, Finding, Snapshot

_RGB = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", re.I)
_HEX = re.compile(r"#([0-9a-f]{3}|[0-9a-f]{6})\b", re.I)


def check_dom(snapshot: Snapshot, *, small_font_px: float = 12) -> list[Finding]:
    """Evaluate implemented geometry, image, and accessibility P0 rules."""
    if small_font_px <= 0:
        raise ValueError("small_font_px must be positive")
    found: list[Finding] = []
    elements = [item for item in snapshot.elements if item.visible]
    found.extend(_check_large_fixed_overlays(snapshot, elements))
    found.extend(_check_overlaps(snapshot, elements))

    width = snapshot.viewport.get("width")
    height = snapshot.viewport.get("height")
    for item in elements:
        box = _rect(item.bbox)
        if box:
            x, y, w, h = box
            clipped = _outside_parent(item, box)
            horizontal_overflow = width is not None and (x < 0 or x + w > width)
            # Content below the fold is normal scrolling, so only flag content
            # fully outside the top edge; parent clipping is checked separately.
            vertical_outside = height is not None and y + h <= 0
            if clipped or horizontal_overflow or vertical_outside:
                found.append(
                    _finding(
                        "ui_element_clipped_or_offscreen",
                        "UI/UX",
                        "High",
                        item,
                        "Element fits within its visible parent and configured viewport",
                        f"element bounds={item.bbox}; viewport={snapshot.viewport}",
                        snapshot,
                    )
                )
            if item.interactive and (w < 24 or h < 24):
                found.append(
                    _finding(
                        "ui_target_minimum_24px",
                        "UI/UX",
                        "Medium",
                        item,
                        "interactive target width and height >= 24 CSS px",
                        f"{w:g} x {h:g} CSS px",
                        snapshot,
                    )
                )
        if item.font_size_px is not None and item.font_size_px < small_font_px:
            found.append(
                _finding(
                    "ui_minimum_font_size",
                    "UI/UX",
                    "Low",
                    item,
                    f"font size >= {small_font_px:g} CSS px",
                    f"{item.font_size_px:g} CSS px",
                    snapshot,
                )
            )
        found.extend(_check_image(snapshot, item, width))
        found.extend(_check_accessibility(snapshot, item))

    if width is not None and snapshot.document_width is not None:
        if snapshot.document_width > width:
            found.append(
                _finding(
                    "ui_no_horizontal_document_overflow",
                    "UI/UX",
                    "High",
                    None,
                    f"document width <= viewport width ({width}px)",
                    f"document width {snapshot.document_width}px",
                    snapshot,
                )
            )
    unique: dict[tuple[str, str | None], Finding] = {}
    for finding in found:
        unique.setdefault((finding.rule, finding.selector), finding)
    return list(unique.values())


def _check_large_fixed_overlays(
    snapshot: Snapshot, elements: list[ElementObservation]
) -> list[Finding]:
    """Flag large, high-stacking fixed layers for human review.

    A landing-page scan cannot know whether a login, consent, or promotion
    dialog was requested. The finding is therefore explicitly advisory.
    Small chat bubbles and ordinary sticky headers are ignored.
    """
    width = snapshot.viewport.get("width")
    height = snapshot.viewport.get("height")
    if not width or not height:
        return []
    findings: list[Finding] = []
    for item in elements:
        coverage = _overlay_coverage(item, width, height)
        prominent = item.z_index is not None and item.z_index >= 10
        if coverage < 0.18 or (not prominent and coverage < 0.5):
            continue
        role = item.role or "no semantic dialog role"
        modal = "; aria-modal=true" if item.aria_modal else ""
        actual = (
            f"fixed layer covers {coverage:.0%} of the viewport; "
            f"z-index={item.z_index if item.z_index is not None else 'auto'}; "
            f"role={role}{modal}. Review whether it is intentional and dismissible."
        )
        findings.append(
            _finding(
                "ui_large_fixed_overlay_review",
                "UI/UX",
                "Medium",
                item,
                "No unrequested fixed layer blocks primary page content; intended dialogs are accessible and dismissible",
                actual,
                snapshot,
            )
        )
    return findings


def _check_overlaps(snapshot: Snapshot, elements: list[ElementObservation]) -> list[Finding]:
    overlays = [
        element for element in elements if _is_large_fixed_overlay(element, snapshot.viewport)
    ]
    relevant = [
        element
        for element in elements
        if (element.interactive or element.text.strip())
        and not _covered_by_overlay(element, overlays)
    ]
    findings: list[Finding] = []
    for index, first in enumerate(relevant):
        first_rect = _rect(first.bbox)
        if not first_rect:
            continue
        for second in relevant[index + 1 :]:
            second_rect = _rect(second.bbox)
            if not second_rect or _related(first, second):
                continue
            if _overlap_ratio(first_rect, second_rect) >= 0.2:
                finding = _finding(
                    "ui_unexpected_visible_overlap",
                    "UI/UX",
                    "High",
                    second,
                    "Relevant visible controls/text do not substantially overlap",
                    f"substantial overlap with another visible element at {second.bbox}",
                    snapshot,
                )
                finding.title = "Unexpected visible overlap"
                findings.append(finding)
    return findings


def _is_large_fixed_overlay(item: ElementObservation, viewport: dict[str, int]) -> bool:
    width, height = viewport.get("width"), viewport.get("height")
    if not width or not height or item.position.lower() != "fixed":
        return False
    coverage = _overlay_coverage(item, width, height)
    return coverage >= 0.18 and (
        (item.z_index is not None and item.z_index >= 10) or coverage >= 0.5
    )


def _overlay_coverage(item: ElementObservation, width: int, height: int) -> float:
    if item.position.lower() != "fixed":
        return 0.0
    box = _rect(item.bbox)
    if not box:
        return 0.0
    x, y, box_width, box_height = box
    visible_width = max(0, min(x + box_width, width) - max(x, 0))
    visible_height = max(0, min(y + box_height, height) - max(y, 0))
    return visible_width * visible_height / (width * height)


def _covered_by_overlay(
    item: ElementObservation, overlays: list[ElementObservation]
) -> bool:
    item_box = _rect(item.bbox)
    if not item_box:
        return False
    for overlay in overlays:
        if overlay is item or item.selector.startswith(overlay.selector + " >"):
            return True
        overlay_box = _rect(overlay.bbox)
        if (
            overlay_box
            and (overlay.z_index or 0) > (item.z_index or 0)
            and _overlap_ratio(overlay_box, item_box) >= 0.5
        ):
            return True
    return False


def _check_image(
    snapshot: Snapshot, item: ElementObservation, viewport_width: int | None
) -> list[Finding]:
    if item.tag.lower() != "img":
        return []
    result: list[Finding] = []
    if item.image_loaded is False or item.natural_width == 0:
        result.append(
            _finding(
                "image_loads_successfully",
                "Image",
                "High",
                item,
                "image resource loads with non-zero natural dimensions",
                "image failed to load",
                snapshot,
            )
        )
    box = _rect(item.bbox)
    if box and item.natural_width and item.natural_height and item.object_fit == "fill":
        _, _, rendered_w, rendered_h = box
        natural_ratio = item.natural_width / item.natural_height
        rendered_ratio = rendered_w / rendered_h if rendered_h else 0
        if rendered_ratio and abs(rendered_ratio / natural_ratio - 1) > 0.05:
            result.append(
                _finding(
                    "image_aspect_ratio_preserved",
                    "Image",
                    "Medium",
                    item,
                    "rendered ratio close to natural ratio "
                    f"{natural_ratio:.3f} or object-fit explains crop",
                    f"rendered ratio {rendered_ratio:.3f}; object-fit={item.object_fit}",
                    snapshot,
                )
            )
        parent = _rect(item.parent_bbox)
        overflow = viewport_width is not None and box[0] + box[2] > viewport_width
        if parent:
            overflow = overflow or box[0] < parent[0] or box[0] + box[2] > parent[0] + parent[2]
        if overflow:
            result.append(
                _finding(
                    "image_fits_container_and_viewport",
                    "Image",
                    "High",
                    item,
                    "image fits its container and viewport",
                    f"image bounds={item.bbox}",
                    snapshot,
                )
            )
    meaningful = not item.decorative
    if meaningful and (item.alt is None or item.alt.strip() == ""):
        result.append(
            _finding(
                "image_meaningful_alt_text",
                "Image",
                "Medium",
                item,
                "meaningful image has a non-empty alt text",
                "alt text is missing or empty",
                snapshot,
            )
        )
    return result


def _check_accessibility(snapshot: Snapshot, item: ElementObservation) -> list[Finding]:
    tag = item.tag.lower()
    result: list[Finding] = []
    if item.color and item.background_color and item.font_size_px is not None:
        foreground, background = _color(item.color), _color(item.background_color)
        if foreground is not None and background is not None:
            large = item.font_size_px >= 24 or (
                item.font_size_px >= 18.67 and item.font_weight in {"bold", "700", "800", "900"}
            )
            minimum = 3.0 if large else 4.5
            ratio = _contrast(foreground, background)
            if ratio < minimum:
                result.append(
                    _finding(
                        "a11y_text_contrast",
                        "Accessibility",
                        "High",
                        item,
                        f"text contrast >= {minimum:.1f}:1",
                        f"observed contrast {ratio:.2f}:1",
                        snapshot,
                    )
                )
    if tag in {"input", "select", "textarea"} and item.has_label is False:
        result.append(
            _finding(
                "a11y_form_control_has_name",
                "Accessibility",
                "High",
                item,
                "form control has an accessible label or name",
                "no accessible label/name",
                snapshot,
            )
        )
    if tag in {"button", "a"} and not (item.accessible_name or item.text).strip():
        result.append(
            _finding(
                "a11y_interactive_control_has_name",
                "Accessibility",
                "High",
                item,
                "button or link has an accessible name",
                "accessible name is empty",
                snapshot,
            )
        )
    return result


def _finding(
    rule: str,
    category: str,
    severity: str,
    element: ElementObservation | None,
    expected: str,
    observed: str,
    snapshot: Snapshot,
) -> Finding:
    selector = element.selector if element else None
    return Finding(
        rule=rule,
        expected=expected,
        actual=observed,
        details=observed,
        severity=severity,
        category=category,
        title=rule.replace("_", " ").capitalize(),
        selector=selector,
        page_url=snapshot.url,
        viewport=dict(snapshot.viewport),
        observed_values=(
            element.to_dict() if element else {"document_width": snapshot.document_width}
        ),
        bug_id=f"{rule}:{selector or snapshot.url}",
    )


def _rect(value: dict[str, float]) -> tuple[float, float, float, float] | None:
    try:
        x, y = float(value["x"]), float(value["y"])
        width, height = (
            float(value.get("width", value.get("w"))),
            float(value.get("height", value.get("h"))),
        )
    except (KeyError, TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return x, y, width, height


def _outside_parent(item: ElementObservation, box: tuple[float, float, float, float]) -> bool:
    if not item.parent_clips:
        return False
    parent = _rect(item.parent_bbox)
    if not parent:
        return False
    x, y, width, height = box
    px, py, pwidth, pheight = parent
    return x < px or y < py or x + width > px + pwidth or y + height > py + pheight


def _related(first: ElementObservation, second: ElementObservation) -> bool:
    return (
        first.selector == second.selector
        or second.selector.startswith(first.selector + " >")
        or first.selector.startswith(second.selector + " >")
        or first.parent_selector == second.selector
        or second.parent_selector == first.selector
        or (
            first.parent_selector
            and first.parent_selector == second.parent_selector
            and _contains(_rect(first.bbox), _rect(second.bbox))
        )
        or (
            first.parent_selector
            and first.parent_selector == second.parent_selector
            and _contains(_rect(second.bbox), _rect(first.bbox))
        )
    )


def _contains(
    outer: tuple[float, float, float, float] | None, inner: tuple[float, float, float, float] | None
) -> bool:
    if not outer or not inner:
        return False
    x, y, w, h = outer
    ix, iy, iw, ih = inner
    return x <= ix and y <= iy and x + w >= ix + iw and y + h >= iy + ih


def _overlap_ratio(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    intersection = max(0, min(ax + aw, bx + bw) - max(ax, bx)) * max(
        0, min(ay + ah, by + bh) - max(ay, by)
    )
    smaller = min(aw * ah, bw * bh)
    return intersection / smaller if smaller else 0


def _color(value: str) -> tuple[int, int, int] | None:
    if value.strip().lower().startswith("rgba(") and not re.search(
        r",\s*1(?:\.0+)?\s*\)$", value.strip()
    ):
        return None
    match = _RGB.search(value)
    if match:
        return tuple(int(channel) for channel in match.groups())
    match = _HEX.search(value)
    if not match:
        return None
    digits = match.group(1)
    if len(digits) == 3:
        digits = "".join(char * 2 for char in digits)
    return tuple(int(digits[index : index + 2], 16) for index in (0, 2, 4))


def _contrast(foreground: Iterable[int], background: Iterable[int]) -> float:
    def luminance(rgb: Iterable[int]) -> float:
        channels = [value / 255 for value in rgb]
        linear = [
            value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
            for value in channels
        ]
        return sum(
            channel * weight
            for channel, weight in zip(linear, (0.2126, 0.7152, 0.0722), strict=True)
        )

    first, second = luminance(foreground), luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)
