from contextlib import contextmanager

import pytest

from bugsafari.config import load_settings
from bugsafari.engine import runner
from bugsafari.engine.target import ResolvedTarget
from bugsafari.reporting.models import (
    ActionRecord,
    Finding,
    RunStatus,
    Snapshot,
)
from bugsafari.reporting.store import RunStore
from bugsafari.scenarios.model import Scenario, TargetSpec

pytestmark = pytest.mark.unit


def test_managed_demo_report_uses_configured_demo_base_url(tmp_path, monkeypatch):
    settings = load_settings(
        {
            "BUGSAFARI_DEMO_BASE_URL": "http://127.0.0.1:5000",
            "BUGSAFARI_RUNS_DIR": str(tmp_path / "runs"),
            "BUGSAFARI_ARTIFACT_DIR": str(tmp_path / "artifacts"),
        }
    )
    managed_url = "http://127.0.0.1:62136"
    action = ActionRecord(
        action="open",
        target=managed_url,
        value=None,
        result="ok",
    )
    finding = Finding(
        rule="test_rule",
        expected="expected",
        actual="actual",
        page_url=f"{managed_url}/cart",
        reproduction_steps=[action],
    )
    scenario = Scenario(
        id="test",
        name="Test scenario",
        description="A test scenario",
        target=TargetSpec(kind="local_demo"),
        steps=(),
    )
    seen_urls = []

    @contextmanager
    def resolve_target(*_args, **_kwargs):
        yield ResolvedTarget(url=managed_url, managed=True)

    @contextmanager
    def playwright_context():
        yield object()

    class Browser:
        def close(self):
            pass

    def attempt(_browser, url, *_args, **_kwargs):
        seen_urls.append(url)
        return runner.Attempt(
            status=RunStatus.BUG_DETECTED,
            actions=[action],
            snapshot=Snapshot(url=f"{managed_url}/cart"),
            findings=[finding],
        )

    monkeypatch.setattr(runner, "resolve_target", resolve_target)
    monkeypatch.setattr(runner, "sync_playwright", playwright_context)
    monkeypatch.setattr(runner, "launch_browser", lambda *_args: Browser())
    monkeypatch.setattr(runner, "_attempt", attempt)

    result = runner.run_scenario(scenario, settings, minimize=False)
    stored = RunStore(settings.runs_dir).load(result.run_id)

    assert seen_urls == [managed_url]
    assert "http://127.0.0.1:5000/cart" in stored.report
    assert "http://127.0.0.1:5000" in stored.report
    assert "62136" not in stored.report
    assert stored.snapshot is not None
    assert stored.snapshot.url == "http://127.0.0.1:5000/cart"
    assert stored.findings[0].page_url == "http://127.0.0.1:5000/cart"
    assert stored.actions[0].target == "http://127.0.0.1:5000"
