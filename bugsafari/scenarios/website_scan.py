"""Build a safe, read-only landing-page audit scenario for a website URL."""

from __future__ import annotations

from urllib.parse import urlsplit

from bugsafari.scenarios.model import Scenario, Step, TargetSpec


def website_scan_scenario(url: str) -> Scenario:
    """Create a single-navigation scan for a caller-provided HTTP(S) website.

    This deliberately performs no form submissions or other state-changing
    actions. It observes the loaded page with the existing DOM checkers.
    """
    normalized = url.strip()
    try:
        parsed = urlsplit(normalized)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Enter a valid website URL") from exc
    if port is not None and not 1 <= port <= 65_535:
        raise ValueError("Website URL port must be between 1 and 65535")
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Enter a complete website URL beginning with http:// or https://")
    if parsed.username or parsed.password:
        raise ValueError("Website URLs must not contain embedded credentials")

    return Scenario(
        id="website-scan",
        name="Website landing-page audit",
        description=f"Run deterministic DOM checks on {normalized}",
        target=TargetSpec(kind="url", url=normalized),
        steps=(Step(action="open", label="Open the supplied website"),),
        invariants=(),
    )
