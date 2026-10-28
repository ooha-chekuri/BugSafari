import pytest

from bugsafari.scenarios.website_scan import website_scan_scenario

pytestmark = pytest.mark.unit


def test_website_scan_targets_the_supplied_site_without_demo_actions():
    scenario = website_scan_scenario("  https://shop.example.test/catalog  ")

    assert scenario.target.kind == "url"
    assert scenario.target.url == "https://shop.example.test/catalog"
    assert scenario.step_actions() == ["open"]
    assert scenario.invariants == ()


@pytest.mark.parametrize(
    "url",
    [
        "",
        "example.test",
        "file:///tmp/page",
        "javascript:alert(1)",
        "https://user:pass@example.test",
    ],
)
def test_website_scan_rejects_invalid_or_credential_urls(url):
    with pytest.raises(ValueError, match="URL"):
        website_scan_scenario(url)


def test_website_scan_rejects_malformed_ports():
    with pytest.raises(ValueError, match="valid website URL"):
        website_scan_scenario("https://example.test:bad")
