"""Launch a Chromium-compatible browser, falling back to an installed one.

A fresh checkout cannot always download Playwright's bundled Chromium (offline
machines, restricted networks, stale browser revisions). Rather than failing with
an opaque driver error, try the bundled build first and then the browsers users
already have. The chosen channel is reported by ``doctor``.
"""

from __future__ import annotations

from playwright.sync_api import Browser, Playwright

from bugsafari.config import Settings

FALLBACK_CHANNELS = ("chrome", "msedge")


class BrowserLaunchError(RuntimeError):
    """No Chromium-compatible browser could be started."""


def launch_browser(playwright: Playwright, settings: Settings) -> Browser:
    """Launch headless/headed Chromium, preferring the configured channel."""
    attempts: list[str | None] = []
    if settings.browser_channel:
        attempts.append(settings.browser_channel)
    attempts.append(None)  # Playwright's bundled build
    attempts.extend(
        channel for channel in FALLBACK_CHANNELS if channel != settings.browser_channel
    )

    failures: list[str] = []
    for channel in attempts:
        label = channel or "bundled chromium"
        try:
            return playwright.chromium.launch(headless=settings.headless, channel=channel)
        except Exception as exc:  # noqa: BLE001 - try the next candidate, report all
            failures.append(f"{label}: {_first_line(exc)}")

    details = "\n  ".join(failures)
    raise BrowserLaunchError(
        "No Chromium-compatible browser could be launched. Run "
        "`python -m playwright install chromium`, or set "
        "BUGSAFARI_BROWSER_CHANNEL to an installed channel (chrome, msedge).\n"
        f"  {details}"
    )


def _first_line(exc: BaseException) -> str:
    text = str(exc).strip().splitlines()
    return text[0] if text else exc.__class__.__name__
