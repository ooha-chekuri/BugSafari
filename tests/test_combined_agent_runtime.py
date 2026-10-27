
from bugsafari.engine.agent_runtime import (
    CombinedAgentWorker,
    run_agents,
)
from bugsafari.engine.multi_agent import AgentResult, AgentTask


class FakeWorker:
    def __init__(self, mode):
        self.mode = mode
        self.calls = []

    def __call__(self, task):
        self.calls.append(task.agent_id)
        return AgentResult(
            agent_id=task.agent_id,
            status="completed",
        )


def test_combined_worker_dispatches_by_mode():
    http_worker = FakeWorker("http")
    browser_worker = FakeWorker("browser")

    worker = CombinedAgentWorker(
        http_worker=http_worker,
        browser_worker=browser_worker,
    )

    http_task = AgentTask(
        agent_id="agent_http",
        mode="http",
        goal="Check HTTP responses",
    )
    browser_task = AgentTask(
        agent_id="agent_browser",
        mode="browser",
        goal="Inspect browser behavior",
    )

    assert worker(http_task).status == "completed"
    assert worker(browser_task).status == "completed"
    assert http_worker.calls == ["agent_http"]
    assert browser_worker.calls == ["agent_browser"]


def test_run_agents_creates_both_agent_types(monkeypatch, tmp_path):
    import bugsafari.engine.agent_runtime as runtime

    class FakeHTTPWorker:
        def __init__(self, **kwargs):
            pass

        def __call__(self, task):
            return AgentResult(task.agent_id, "completed")

    class FakeBrowserWorker:
        def __init__(self, **kwargs):
            pass

        def __call__(self, task):
            return AgentResult(task.agent_id, "completed")

    monkeypatch.setattr(runtime, "HTTPProbeWorker", FakeHTTPWorker)
    monkeypatch.setattr(runtime, "BrowserAgentWorker", FakeBrowserWorker)

    report = run_agents(
        "http://localhost:5000",
        count=4,
        browser_ratio=0.5,
        max_concurrency=2,
        artifact_dir=tmp_path,
    )

    assert report.requested_agents == 4
    assert report.completed_agents == 4
    assert report.failed_agents == 0
    assert len(report.agent_results) == 4


def test_run_agents_rejects_invalid_browser_ratio():
    import pytest

    with pytest.raises(ValueError, match="browser_ratio"):
        run_agents(
            "http://localhost:5000",
            count=2,
            browser_ratio=1.5,
        )
