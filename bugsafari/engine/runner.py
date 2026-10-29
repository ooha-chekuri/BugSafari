"""Compose one exploration run: target, browser, steps, snapshot, rules, storage."""

from __future__ import annotations

import platform
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from importlib import metadata
from pathlib import Path
from time import monotonic

from playwright.sync_api import Browser, sync_playwright

from bugsafari.browser.controller import BrowserController
from bugsafari.browser.launch import launch_browser
from bugsafari.browser.snapshot import capture_snapshot
from bugsafari.config import Settings, load_settings
from bugsafari.detection.dom_checks import check_dom
from bugsafari.detection.engine import evaluate
from bugsafari.engine.executor import Executor
from bugsafari.engine.minimizer import MinimizeResult, minimize_steps
from bugsafari.engine.planner import ScriptedPlanner, SeededRandomPlanner
from bugsafari.engine.target import AppFactory, resolve_target
from bugsafari.reporting.models import (
    ActionRecord,
    Finding,
    RunResult,
    RunStatus,
    Snapshot,
)
from bugsafari.reporting.store import RunStore, new_run_id, utc_now
from bugsafari.scenarios.model import Scenario, Step


@dataclass
class Attempt:
    """The outcome of one browser pass over a step sequence."""

    status: RunStatus
    actions: list[ActionRecord] = field(default_factory=list)
    snapshot: Snapshot | None = None
    findings: list[Finding] = field(default_factory=list)
    error: str | None = None
    screenshot: str | None = None


def run_scenario(
    scenario: Scenario,
    settings: Settings | None = None,
    *,
    app_factory: AppFactory | None = None,
    steps: Sequence[Step] | None = None,
    screenshot_path: str | Path | None = None,
    minimize: bool | None = None,
) -> RunResult:
    """Execute a scenario end to end and store a reproducible report."""
    settings = settings or load_settings()
    settings.ensure_dirs()
    store = RunStore(settings.runs_dir)

    if steps is not None:
        planned = tuple(steps)
    elif settings.planner == "seeded_random":
        planned = tuple(SeededRandomPlanner(scenario, seed=settings.seed).plan())
    else:
        planned = tuple(ScriptedPlanner(scenario).steps)

    result = RunResult(
        status=RunStatus.EXECUTION_ERROR,
        run_id=new_run_id(),
    )
    started_at = utc_now()
    started = monotonic()
    snapshot: Snapshot | None = None

    shot_target = Path(screenshot_path) if screenshot_path else settings.artifact_dir / "latest.png"

    try:
        with resolve_target(scenario.target, settings, app_factory) as target:
            with sync_playwright() as playwright:
                browser = launch_browser(playwright, settings)

                try:
                    attempt = _attempt(
                        browser,
                        target.url,
                        planned,
                        scenario,
                        settings,
                        screenshot_path=shot_target,
                    )

                    result.status = attempt.status
                    result.actions = attempt.actions
                    result.findings = attempt.findings
                    result.finding = attempt.findings[0] if attempt.findings else None
                    result.error = attempt.error
                    result.screenshot = attempt.screenshot
                    snapshot = attempt.snapshot

                    should_minimize = settings.minimize if minimize is None else minimize

                    if attempt.findings and should_minimize:
                        minimized_actions, minimization_stats = _minimize(
                            browser,
                            target.url,
                            planned,
                            scenario,
                            settings,
                            attempt,
                        )
                        result.minimized_actions = minimized_actions
                        result.minimization_stats = minimization_stats

                    if target.managed:
                        snapshot = _rewrite_managed_demo_urls(
                            result,
                            snapshot,
                            target.url,
                            settings.demo_base_url,
                        )

                finally:
                    browser.close()

    except Exception as exc:  # noqa: BLE001
        result.status = RunStatus.EXECUTION_ERROR
        result.error = f"{type(exc).__name__}: {_first_line(exc)}"

    try:
        stored = store.save(
            result=result,
            scenario=scenario,
            snapshot=snapshot,
            environment=_environment(settings),
            started_at=started_at,
            duration_s=monotonic() - started,
            screenshot_path=result.screenshot,
        )
    except Exception as exc:  # noqa: BLE001
        result.error = _join(
            result.error,
            f"could not save report: {_first_line(exc)}",
        )
        return result

    if stored.screenshot:
        result.screenshot = str(store.run_dir(stored.run_id) / stored.screenshot)

    return result


def _minimize(
    browser: Browser,
    url: str,
    steps: Sequence[Step],
    scenario: Scenario,
    settings: Settings,
    attempt: Attempt,
) -> tuple[list[ActionRecord] | None, dict[str, object]]:
    """Minimize a failing sequence and retain diagnostic statistics."""
    target_finding = attempt.findings[0]

    def reproduce(candidate: tuple[Step, ...]) -> Finding | None:
        replay = _attempt(
            browser,
            url,
            candidate,
            scenario,
            settings,
            screenshot_path=None,
        )

        return replay.findings[0] if replay.findings else None

    outcome: MinimizeResult = minimize_steps(
        steps,
        reproduce,
        target_finding.signature(),
        max_attempts=settings.max_minimize_attempts,
        timeout_s=min(60.0, float(settings.run_timeout_s)),
    )

    stats: dict[str, object] = {
        "original_step_count": len(outcome.original),
        "minimized_step_count": len(outcome.minimized),
        "attempts": outcome.attempts,
        "duration_s": outcome.duration_s,
        "budget_exhausted": outcome.exhausted,
        "changed": outcome.changed,
        "same_finding_preserved": None,
    }

    # If the sequence did not change, no shorter sequence is returned.
    if not outcome.changed:
        return None, stats

    # Re-run the proposed minimized sequence before accepting it.
    replay = _attempt(
        browser,
        url,
        outcome.minimized,
        scenario,
        settings,
        screenshot_path=None,
    )

    reproduced = any(
        finding.signature() == target_finding.signature() for finding in replay.findings
    )

    stats["same_finding_preserved"] = reproduced

    if not reproduced:
        return None, stats

    return replay.actions, stats


def _attempt(
    browser: Browser,
    url: str,
    steps: Sequence[Step],
    scenario: Scenario,
    settings: Settings,
    screenshot_path: Path | None,
) -> Attempt:
    """Run one sequence in a fresh context so state never leaks."""
    context = browser.new_context()
    page = context.new_page()
    controller = BrowserController(page, settings.action_timeout_ms)

    try:
        execution = Executor(controller, settings, url).run(list(steps))

        if not execution.ok:
            return Attempt(
                status=RunStatus.EXECUTION_ERROR,
                actions=list(controller.actions),
                error=str(execution.error),
                screenshot=_screenshot(controller, screenshot_path),
            )

        include_shop_data = (
            scenario.target.kind == "local_demo"
            or bool(scenario.capture)
            or bool(scenario.invariants)
        )
        snapshot = capture_snapshot(page, scenario.capture, include_shop_data=include_shop_data)
        evaluation = evaluate(
            snapshot,
            scenario.invariants,
            controller.actions,
            small_font_px=settings.small_font_px,
        )
        original_viewport = page.viewport_size
        responsive_keys = {(finding.rule, finding.selector) for finding in evaluation.findings}
        for viewport_width in (375, 768, 1280):
            page.set_viewport_size({"width": viewport_width, "height": 812})
            responsive_snapshot = capture_snapshot(page, include_shop_data=include_shop_data)
            for finding in check_dom(responsive_snapshot, small_font_px=settings.small_font_px):
                finding.reproduction_steps = list(controller.actions)
                key = (finding.rule, finding.selector)
                if key not in responsive_keys:
                    evaluation.findings.append(finding)
                    responsive_keys.add(key)
        if original_viewport is not None:
            page.set_viewport_size(original_viewport)
        shot = _screenshot(controller, screenshot_path)

        if evaluation.confirmed:
            return Attempt(
                status=RunStatus.BUG_DETECTED,
                actions=list(controller.actions),
                snapshot=snapshot,
                findings=evaluation.findings,
                screenshot=shot,
            )

        if evaluation.errors:
            return Attempt(
                status=RunStatus.EXECUTION_ERROR,
                actions=list(controller.actions),
                snapshot=snapshot,
                error="; ".join(evaluation.errors),
                screenshot=shot,
            )

        return Attempt(
            status=RunStatus.PASSED,
            actions=list(controller.actions),
            snapshot=snapshot,
            screenshot=shot,
        )

    except Exception as exc:  # noqa: BLE001
        return Attempt(
            status=RunStatus.EXECUTION_ERROR,
            actions=list(controller.actions),
            error=f"{type(exc).__name__}: {_first_line(exc)}",
            screenshot=_screenshot(controller, screenshot_path),
        )

    finally:
        context.close()


def _rewrite_managed_demo_urls(
    result: RunResult,
    snapshot: Snapshot | None,
    managed_url: str,
    configured_url: str,
) -> Snapshot | None:
    """Replace the temporary managed-server origin in persisted run data."""
    for action in result.actions + (result.minimized_actions or []):
        action.target = _replace_url_origin(action.target, managed_url, configured_url)

    for finding in result.findings:
        if finding.page_url:
            finding.page_url = _replace_url_origin(
                finding.page_url,
                managed_url,
                configured_url,
            )
        for action in finding.reproduction_steps:
            action.target = _replace_url_origin(action.target, managed_url, configured_url)

    if snapshot is not None:
        snapshot = replace(
            snapshot,
            url=_replace_url_origin(snapshot.url, managed_url, configured_url),
        )
    return snapshot


def _replace_url_origin(value: str, original: str, replacement: str) -> str:
    if value == original:
        return replacement
    if value.startswith((f"{original}/", f"{original}?", f"{original}#")):
        return replacement.rstrip("/") + value[len(original) :]
    return value


def _screenshot(
    controller: BrowserController,
    path: Path | None,
) -> str | None:
    if path is None:
        return None

    try:
        return controller.screenshot(path)
    except Exception:  # noqa: BLE001
        return None


def _environment(settings: Settings) -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "playwright": _version("playwright"),
        "headless": str(settings.headless).lower(),
        "browser_channel": settings.browser_channel or "bundled-first",
        "action_timeout_ms": str(settings.action_timeout_ms),
    }


def _version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:  # pragma: no cover
        return "unknown"


def _first_line(exc: BaseException) -> str:
    lines = str(exc).strip().splitlines()
    return lines[0] if lines else exc.__class__.__name__


def _join(left: str | None, right: str) -> str:
    return f"{left}; {right}" if left else right
