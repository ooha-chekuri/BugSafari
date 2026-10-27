
"""Browser worker for local BugSafari browser testing."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from bugsafari.browser.controller import BrowserController
from bugsafari.browser.launch import launch_browser
from bugsafari.config import load_settings
from bugsafari.engine.multi_agent import (
    AgentResult,
    AgentTask,
    FindingReport,
)
from bugsafari.money import parse_money


class BrowserAgentWorker:
    """Inspect a local page and test the demo shop's cart totals."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_ms: int = 5000,
        artifact_dir: str | Path = "artifacts/browser_agents",
    ) -> None:
        parsed = urlparse(base_url)

        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Target URL must use http:// or https://")

        if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError(
                "Browser agent only allows localhost or loopback IPs"
            )

        if timeout_ms < 1:
            raise ValueError("timeout_ms must be positive")

        self.base_url = base_url
        self.timeout_ms = timeout_ms
        self.artifact_dir = Path(artifact_dir)

    def __call__(self, task: AgentTask) -> AgentResult:
        if task.mode != "browser":
            return AgentResult(
                agent_id=task.agent_id,
                status="completed",
            )

        page_errors: list[str] = []
        console_errors: list[str] = []
        actions: list[str] = []
        findings: list[FindingReport] = []

        try:
            settings = load_settings()

            with sync_playwright() as playwright:
                browser = launch_browser(playwright, settings)

                try:
                    context = browser.new_context()
                    try:
                        page = context.new_page()
                        page.set_default_timeout(self.timeout_ms)
                        page.set_default_navigation_timeout(
                            self.timeout_ms * 4
                        )

                        page.on(
                            "pageerror",
                            lambda error: page_errors.append(str(error)),
                        )
                        page.on(
                            "console",
                            lambda message: console_errors.append(
                                message.text
                            )
                            if message.type == "error"
                            else None,
                        )

                        controller = BrowserController(
                            page,
                            action_timeout_ms=self.timeout_ms,
                        )
                        controller.open(self.base_url)

                        # Exercise the known demo-shop cart scenario.
                        product = page.locator(
                            '[data-product="trail-mug"]'
                        )
                        if product.count() > 0:
                            controller.click("add-trail-mug")
                            controller.change_quantity(
                                "quantity-trail-mug", 2
                            )

                            line_total = controller.read(
                                "line-total-trail-mug"
                            )
                            cart_total = controller.read("total")

                            expected_cents = parse_money(line_total)
                            actual_cents = parse_money(cart_total)

                            if expected_cents is None:
                                raise ValueError(
                                    "Trail Mug line total is not a valid "
                                    f"money amount: {line_total!r}"
                                )
                            if actual_cents is None:
                                raise ValueError(
                                    "Cart total is not a valid money "
                                    f"amount: {cart_total!r}"
                                )

                            actions.extend(
                                f"{action.action}: {action.target}"
                                + (
                                    f" = {action.value}"
                                    if action.value is not None
                                    else ""
                                )
                                for action in controller.actions
                            )

                            if expected_cents != actual_cents:
                                findings.append(
                                    FindingReport(
                                        title=(
                                            "Cart total does not match "
                                            "the line total"
                                        ),
                                        target=self.base_url,
                                        rule=(
                                            "cart_total_matches_line_total"
                                        ),
                                        expected=line_total,
                                        actual=cart_total,
                                        reproduction_steps=(
                                            f"Open {self.base_url}",
                                            "Add one Trail Mug to the cart",
                                            "Change its quantity to 2",
                                            (
                                                "Observe line total "
                                                f"{line_total} and cart "
                                                f"total {cart_total}"
                                            ),
                                        ),
                                        evidence=(
                                            f"Line total: {line_total}",
                                            f"Cart total: {cart_total}",
                                        ),
                                        suggested_fix=(
                                            "Recalculate aggregate cart "
                                            "totals whenever a quantity "
                                            "changes."
                                        ),
                                    )
                                )

                        # Save a screenshot after the interactions.
                        self.artifact_dir.mkdir(
                            parents=True,
                            exist_ok=True,
                        )
                        screenshot_path = (
                            self.artifact_dir / f"{task.agent_id}.png"
                        )
                        controller.screenshot(screenshot_path)

                        actions.extend(
                            f"{action.action}: {action.target}"
                            + (
                                f" = {action.value}"
                                if action.value is not None
                                else ""
                            )
                            for action in controller.actions
                            if action.action != "open"
                        )

                    finally:
                        context.close()
                finally:
                    browser.close()

            if page_errors:
                findings.append(
                    FindingReport(
                        title="Uncaught browser JavaScript error",
                        target=self.base_url,
                        rule="page_has_no_uncaught_javascript_errors",
                        expected="No uncaught JavaScript errors",
                        actual="; ".join(page_errors[:5]),
                        reproduction_steps=(f"Open {self.base_url}",),
                        evidence=tuple(page_errors[:5]),
                        suggested_fix=(
                            "Inspect the browser stack trace and fix the "
                            "underlying JavaScript exception."
                        ),
                    )
                )

            if console_errors:
                findings.append(
                    FindingReport(
                        title="Browser console error",
                        target=self.base_url,
                        rule="page_console_has_no_errors",
                        expected="No unexpected console errors",
                        actual="; ".join(console_errors[:5]),
                        reproduction_steps=(f"Open {self.base_url}",),
                        evidence=tuple(console_errors[:5]),
                        suggested_fix=(
                            "Inspect the console messages and determine "
                            "whether they indicate an application defect."
                        ),
                    )
                )

            return AgentResult(
                agent_id=task.agent_id,
                status="completed",
                findings=tuple(findings),
            )

        except Exception as exc:
            return AgentResult(
                agent_id=task.agent_id,
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
            )
