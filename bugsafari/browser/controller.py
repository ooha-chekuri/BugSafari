"""Small Playwright controller that records bounded browser actions.

Timeouts are configured once on the page, so a missing selector fails fast and
predictably instead of hanging for Playwright's default 30 seconds per call.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page

from bugsafari.reporting.models import ActionRecord

NAVIGATION_TIMEOUT_FACTOR = 4


class BrowserController:
    """Perform stable, accessible interactions and keep an action history."""

    def __init__(self, page: Page, action_timeout_ms: int = 5_000):
        self.page = page
        self.action_timeout_ms = action_timeout_ms
        self.actions: list[ActionRecord] = []
        page.set_default_timeout(action_timeout_ms)
        page.set_default_navigation_timeout(action_timeout_ms * NAVIGATION_TIMEOUT_FACTOR)

    def record(
        self, action: str, target: str, value: str | None = None, result: str = "completed"
    ) -> ActionRecord:
        entry = ActionRecord(action=action, target=target, value=value, result=result)
        self.actions.append(entry)
        return entry

    def open(self, url: str) -> None:
        response = self.page.goto(url, wait_until="domcontentloaded")
        if response is None or not response.ok:
            raise RuntimeError(f"could not open {url}")
        self.record("open", url, None, f"HTTP {response.status}")

    def click(self, test_id: str) -> None:
        self.page.get_by_test_id(test_id).click()
        self.record("click", test_id)

    def fill(self, test_id: str, value: str) -> None:
        self.page.get_by_test_id(test_id).fill(value)
        self.record("fill", test_id, value)

    def change_quantity(self, test_id: str, quantity: int | str) -> None:
        """Set a quantity input and commit it, logging a single honest action."""
        locator = self.page.get_by_test_id(test_id)
        locator.fill(str(quantity))
        locator.press("Tab")
        self.record("change_quantity", test_id, str(quantity), "changed and committed")

    def press(self, test_id: str, key: str) -> None:
        self.page.get_by_test_id(test_id).press(key)
        self.record("press", test_id, key)

    def select(self, test_id: str, value: str) -> None:
        self.page.get_by_test_id(test_id).select_option(value)
        self.record("select", test_id, value)

    def wait_visible(self, test_id: str) -> None:
        self.page.get_by_test_id(test_id).wait_for(state="visible")
        self.record("wait_visible", test_id)

    def read(self, test_id: str) -> str:
        return self.page.get_by_test_id(test_id).inner_text().strip()

    def count(self, selector: str) -> int:
        return self.page.locator(selector).count()

    def screenshot(self, path: str | Path) -> str:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(target), full_page=True)
        return str(target)
