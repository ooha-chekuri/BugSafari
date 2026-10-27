
import pytest

from bugsafari.engine.browser_agent_worker import BrowserAgentWorker
from bugsafari.engine.multi_agent import AgentTask


def test_browser_worker_rejects_external_target():
    with pytest.raises(ValueError, match="only allows localhost"):
        BrowserAgentWorker("https://example.com")


def test_browser_worker_skips_http_tasks():
    worker = BrowserAgentWorker("http://localhost:5000")
    task = AgentTask(
        agent_id="agent_001",
        mode="http",
        goal="Probe HTTP response",
    )

    result = worker(task)

    assert result.status == "completed"
    assert result.findings == ()


def test_browser_worker_rejects_invalid_timeout():
    with pytest.raises(ValueError, match="timeout_ms"):
        BrowserAgentWorker(
            "http://localhost:5000",
            timeout_ms=0,
        )
