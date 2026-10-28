"""Deterministic DOM-checker unit coverage independent of a browser."""

import pytest

from bugsafari.detection.dom_checks import check_dom
from bugsafari.reporting.models import ActionRecord, ElementObservation, RunStatus, Snapshot, StoredRun
from bugsafari.reporting.reporter import render_json, render_markdown

pytestmark = pytest.mark.unit


def element(selector: str = "#item", **changes) -> ElementObservation:
    values = {
        "selector": selector,
        "tag": "div",
        "text": "Visible text",
        "bbox": {"x": 10, "y": 10, "width": 100, "height": 40},
        "parent_selector": "#parent",
        "parent_bbox": {"x": 0, "y": 0, "width": 320, "height": 700},
        "font_size_px": 16,
        "color": "rgb(0, 0, 0)",
        "background_color": "rgb(255, 255, 255)",
    }
    values.update(changes)
    return ElementObservation(**values)


def snapshot(*elements: ElementObservation, width=375, height=812, doc_width=None) -> Snapshot:
    return Snapshot(
        url="https://example.test/cart",
        elements=tuple(elements),
        viewport={"width": width, "height": height},
        document_width=doc_width or width,
    )


def rules(findings):
    return {finding.rule for finding in findings}


def test_legacy_snapshot_schema_still_loads_without_dom_data():
    old = Snapshot.from_dict({"url": "https://example.test", "catalog": {}, "cart": {}})
    assert old.elements == ()
    assert old.viewport == {}
    assert old.to_dict()["elements"] == []


def test_dom_observation_and_legacy_severity_round_trip():
    from bugsafari.reporting.models import Finding

    observed = element("#submit", tag="button", interactive=True)
    restored = ElementObservation.from_dict(observed.to_dict())
    assert restored == observed
    finding = Finding.from_dict(
        {
            "rule": "old_rule",
            "expected": "yes",
            "actual": "no",
            "severity": "major",
        }
    )
    assert finding.severity == "High"
    assert finding.category == "Functional"
    assert finding.to_dict()["severity"] == "High"


def test_overlay_observation_round_trips_and_legacy_defaults_are_safe():
    overlay = element(
        "#promotion-layer",
        text="",
        position="fixed",
        z_index=1200,
        role="dialog",
        aria_modal=True,
    )
    assert ElementObservation.from_dict(overlay.to_dict()) == overlay
    legacy = ElementObservation.from_dict({"selector": "#old", "tag": "div"})
    assert legacy.position == "static"
    assert legacy.z_index is None
    assert legacy.role is None
    assert not legacy.aria_modal


def test_text_reports_omit_screenshot_artifacts(tmp_path):
    run = StoredRun(
        run_id="run-20261028T000000Z-abcdef",
        scenario_id="check",
        scenario_name="DOM check",
        status=RunStatus.PASSED,
        started_at="2026-10-28T00:00:00Z",
        duration_s=1,
        screenshot="screenshot.png",
    )
    json_report = render_json(run)
    text_report = render_markdown(run)
    assert "screenshot" not in json_report.lower()
    assert "screenshot" not in text_report.lower()


def test_html_report_uses_text_labels_and_contains_no_images():
    from bugsafari.reporting.models import Finding
    from bugsafari.reporting.reporter import render_html, render_markdown

    run = StoredRun(
        run_id="run-20261028T000000Z-abcdef",
        scenario_id="check",
        scenario_name="DOM check",
        status=RunStatus.BUG_DETECTED,
        started_at="2026-10-28T00:00:00Z",
        duration_s=1,
        findings=[
            Finding(
                rule="a11y_text_contrast",
                expected="contrast >= 4.5:1",
                actual="contrast 2.1:1",
                category="Accessibility",
                severity="high",
                selector="#price",
                page_url="https://example.test",
                reproduction_steps=[
                    ActionRecord(action="open", target="https://example.test", value=None, result="ok")
                ],
            )
        ],
    )
    report = render_html(run)
    markdown = render_markdown(run)
    assert "[HIGH] Accessibility" in report
    assert "[HIGH] Accessibility" in markdown
    assert "contrast 2.1:1" in report
    assert "<li>open https://example.test</li>" in report
    assert "<li>1. open https://example.test</li>" not in report
    assert "<img" not in report.lower()
    assert "data:image" not in report.lower()


def test_small_targets_small_text_and_horizontal_overflow_are_reported():
    target = element(
        "#tiny",
        tag="button",
        interactive=True,
        bbox={"x": 10, "y": 10, "width": 18, "height": 20},
        font_size_px=10,
    )
    findings = check_dom(snapshot(target, doc_width=420))
    assert {
        "ui_target_minimum_24px",
        "ui_minimum_font_size",
        "ui_no_horizontal_document_overflow",
    } <= rules(findings)
    target_finding = next(f for f in findings if f.rule == "ui_target_minimum_24px")
    assert target_finding.category == "UI/UX"
    assert target_finding.severity == "Medium"
    assert target_finding.selector == "#tiny"
    assert target_finding.page_url == "https://example.test/cart"


def test_overlap_ignores_containment_and_hidden_elements():
    parent = element("#parent", bbox={"x": 0, "y": 0, "width": 200, "height": 100})
    child = element(
        "#child", parent_selector="#parent", bbox={"x": 10, "y": 10, "width": 50, "height": 20}
    )
    hidden = element("#hidden", visible=False, bbox={"x": 20, "y": 10, "width": 100, "height": 30})
    assert "ui_unexpected_visible_overlap" not in rules(check_dom(snapshot(parent, child, hidden)))


def test_overlap_ignores_deeply_nested_descendants():
    wrapper = element("#container", text="", bbox={"x": 0, "y": 0, "width": 300, "height": 300})
    link = element(
        "#container > div > div > a",
        tag="a",
        interactive=True,
        text="Product",
        bbox={"x": 20, "y": 20, "width": 120, "height": 32},
        parent_selector="#container > div > div",
    )
    assert "ui_unexpected_visible_overlap" not in rules(check_dom(snapshot(wrapper, link)))


def test_unrelated_visible_controls_with_substantial_overlap_are_reported():
    one = element("#one", tag="button", interactive=True, text="Save")
    two = element(
        "#two",
        tag="button",
        interactive=True,
        text="Cancel",
        bbox={"x": 50, "y": 10, "width": 100, "height": 40},
    )
    finding = next(
        f for f in check_dom(snapshot(one, two)) if f.rule == "ui_unexpected_visible_overlap"
    )
    assert finding.selector == "#two"


def test_large_fixed_overlay_is_reported_as_a_reviewable_finding():
    overlay = element(
        "#promotion-layer",
        text="",
        position="fixed",
        z_index=1200,
        role="dialog",
        aria_modal=True,
        bbox={"x": 0, "y": 0, "width": 375, "height": 812},
    )
    finding = next(
        item
        for item in check_dom(snapshot(overlay))
        if item.rule == "ui_large_fixed_overlay_review"
    )
    assert finding.category == "UI/UX"
    assert finding.severity == "Medium"
    assert "covers 100%" in finding.actual
    assert "aria-modal=true" in finding.actual


def test_small_fixed_widgets_and_sticky_headers_are_not_overlay_findings():
    chat = element(
        "#chat",
        text="Chat",
        position="fixed",
        z_index=1000,
        bbox={"x": 315, "y": 730, "width": 52, "height": 52},
    )
    header = element(
        "#header",
        text="Menu",
        position="sticky",
        z_index=1000,
        bbox={"x": 0, "y": 0, "width": 375, "height": 64},
    )
    assert "ui_large_fixed_overlay_review" not in rules(check_dom(snapshot(chat, header)))


def test_overlay_does_not_create_secondary_overlap_noise():
    overlay = element(
        "#backdrop",
        text="",
        position="fixed",
        z_index=1000,
        bbox={"x": 0, "y": 0, "width": 375, "height": 812},
    )
    page_content = element("#page-copy", bbox={"x": 20, "y": 50, "width": 200, "height": 80})
    found = check_dom(snapshot(overlay, page_content))
    assert "ui_large_fixed_overlay_review" in rules(found)
    assert "ui_unexpected_visible_overlap" not in rules(found)


def test_clipping_is_only_reported_when_parent_clips():
    child = element(
        "#child",
        bbox={"x": 105, "y": 10, "width": 30, "height": 20},
        parent_bbox={"x": 0, "y": 0, "width": 120, "height": 100},
        parent_clips=True,
    )
    assert "ui_element_clipped_or_offscreen" in rules(check_dom(snapshot(child)))
    assert "ui_element_clipped_or_offscreen" not in rules(
        check_dom(
            snapshot(element("#below-fold", bbox={"x": 10, "y": 900, "width": 100, "height": 30}))
        )
    )


def test_image_broken_distorted_overflow_and_missing_alt_are_reported():
    image = element(
        "img.product",
        tag="img",
        text="",
        decorative=False,
        alt=None,
        image_loaded=False,
        natural_width=400,
        natural_height=100,
        bbox={"x": 10, "y": 10, "width": 180, "height": 100},
        parent_bbox={"x": 0, "y": 0, "width": 150, "height": 200},
    )
    assert {
        "image_loads_successfully",
        "image_aspect_ratio_preserved",
        "image_fits_container_and_viewport",
        "image_meaningful_alt_text",
    } <= rules(check_dom(snapshot(image)))


def test_legitimate_object_fit_and_decorative_image_are_not_flagged():
    image = element(
        "img.decorative",
        tag="img",
        text="",
        decorative=True,
        alt="",
        object_fit="cover",
        image_loaded=True,
        natural_width=400,
        natural_height=100,
        bbox={"x": 10, "y": 10, "width": 80, "height": 80},
    )
    assert not rules(check_dom(snapshot(image)))


def test_contrast_and_missing_control_names_are_reported():
    text = element(
        "#low-contrast", color="rgb(190, 190, 190)", background_color="rgb(255, 255, 255)"
    )
    input_field = element("#email", tag="input", text="", has_label=False, accessible_name="")
    button = element("#icon-only", tag="button", text="", interactive=True, accessible_name="")
    found = check_dom(snapshot(text, input_field, button))
    assert {
        "a11y_text_contrast",
        "a11y_form_control_has_name",
        "a11y_interactive_control_has_name",
    } <= rules(found)
    assert all(f.category == "Accessibility" for f in found if f.rule.startswith("a11y_"))


def test_good_contrast_and_named_controls_have_no_accessibility_findings():
    good_text = element("#good", color="rgb(0, 0, 0)", background_color="rgb(255, 255, 255)")
    labelled = element("#email", tag="input", text="", has_label=True, accessible_name="Email")
    named_button = element("#save", tag="button", text="", interactive=True, accessible_name="Save")
    found = check_dom(snapshot(good_text, labelled, named_button))
    assert not {
        "a11y_text_contrast",
        "a11y_form_control_has_name",
        "a11y_interactive_control_has_name",
    } & rules(found)


def test_transparent_color_is_not_treated_as_black_for_contrast():
    transparent = element(background_color="rgba(0, 0, 0, 0)")
    assert "a11y_text_contrast" not in rules(check_dom(snapshot(transparent)))


def test_small_font_threshold_is_configurable_and_must_be_positive():
    item = element(font_size_px=11)
    assert "ui_minimum_font_size" not in rules(check_dom(snapshot(item), small_font_px=10))
    with pytest.raises(ValueError, match="positive"):
        check_dom(snapshot(item), small_font_px=0)
