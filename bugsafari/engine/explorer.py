"""Run the first deterministic BugSafari scenario against the local shop."""

from contextlib import contextmanager
from threading import Thread
from time import monotonic, sleep

from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright

from app.config import DEMO_HOST, SCREENSHOT_PATH
from bugsafari.browser.controller import BrowserController
from bugsafari.detection.invariants import check_cart_total
from bugsafari.reporting.models import RunResult
from demo_app.app import create_app


@contextmanager
def local_demo_server():
    """Start and reliably stop an isolated local Flask server."""
    server = make_server(DEMO_HOST, 0, create_app())
    demo_url = f"http://{DEMO_HOST}:{server.server_port}"
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    deadline = monotonic() + 5
    while monotonic() < deadline:
        try:
            import urllib.request
            urllib.request.urlopen(demo_url, timeout=0.25).close()
            break
        except Exception:
            sleep(0.05)
    else:
        server.shutdown()
        raise RuntimeError("Local demo server did not become ready")
    try:
        yield demo_url
    finally:
        server.shutdown()
        thread.join(timeout=3)


def run_demo_exploration(screenshot_path: str = SCREENSHOT_PATH) -> RunResult:
    """Add one item, raise its quantity, and validate the displayed cart total."""
    result = RunResult(status="execution_error")
    controller = None
    try:
        with local_demo_server() as demo_url, sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                controller = BrowserController(page)
                controller.open(demo_url)
                controller.click("add-trail-mug")
                controller.change_quantity("quantity-trail-mug", 2)
                total = controller.read("total")
                result.screenshot = controller.screenshot(screenshot_path)
                result.actions = controller.actions
                result.finding = check_cart_total(total, {"trail-mug": 1800}, {"trail-mug": 2}, controller.actions)
                result.status = "bug_detected" if result.finding else "passed"
            finally:
                browser.close()
    except Exception as exc:
        if controller is not None:
            result.actions = controller.actions
        result.error = f"{type(exc).__name__}: {exc}"
    return result
