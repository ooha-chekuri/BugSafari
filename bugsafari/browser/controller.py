"""Small Playwright controller that records bounded browser actions."""

from pathlib import Path
from playwright.sync_api import Page
from bugsafari.reporting.models import ActionRecord


class BrowserController:
    """Perform stable, accessible interactions and keep an action history."""

    def __init__(self, page: Page):
        self.page = page
        self.actions: list[ActionRecord] = []

    def open(self, url: str) -> None:
        response = self.page.goto(url, wait_until="domcontentloaded")
        if response is None or not response.ok:
            raise RuntimeError(f"Could not open {url}")
        self.actions.append(ActionRecord("open", url, None, f"HTTP {response.status}"))

    def click(self, test_id: str) -> None:
        self.page.get_by_test_id(test_id).click()
        self.actions.append(ActionRecord("click", test_id, None, "completed"))

    def fill(self, test_id: str, value: str) -> None:
        self.page.get_by_test_id(test_id).fill(value)
        self.actions.append(ActionRecord("fill", test_id, value, "completed"))

    def change_quantity(self, test_id: str, quantity: int) -> None:
        self.fill(test_id, str(quantity))
        self.page.get_by_test_id(test_id).press("Tab")
        self.actions[-1].result = "changed and committed"

    def read(self, test_id: str) -> str:
        return self.page.get_by_test_id(test_id).inner_text().strip()

    def screenshot(self, path: str) -> str:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(target), full_page=True)
        return str(target)
