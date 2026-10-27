from bugsafari.engine.agent_worker import HTTPProbeWorker
from urllib.error import HTTPError
from unittest.mock import MagicMock, patch

import pytest

from bugsafari.engine.agent_worker import HTTPProbeWorker
from bugsafari.engine.multi_agent import AgentTask


def test_worker_rejects_non_local_target():
    with pytest.raises(ValueError, match="only allows localhost"):
        HTTPProbeWorker("https://example.com")


def test_http_worker_does_not_report_successful_response_as_bug():
    worker = HTTPProbeWorker("http://localhost:5000")
    task = AgentTask(
        agent_id="agent_001",
        mode="http",
        goal="Check local homepage",
    )

    response = MagicMock()
    response.status = 200
    response.read.return_value = b"OK"

    with patch("bugsafari.engine.agent_worker.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = response

        result = worker(task)

    assert result.status == "completed"
    assert result.findings == ()
    mock_urlopen.assert_called_once()


def test_http_worker_reports_server_error_as_candidate():
    worker = HTTPProbeWorker("http://127.0.0.1:5000")
    task = AgentTask(
        agent_id="agent_002",
        mode="http",
        goal="Check local endpoint",
    )

    error = HTTPError(
        url="http://127.0.0.1:5000/",
        code=500,
        msg="Internal Server Error",
        hdrs=None,
        fp=None,
    )

    with patch(
        "bugsafari.engine.agent_worker.urlopen",
        side_effect=error,
    ):
        result = worker(task)

    assert len(result.findings) == 1
    assert result.findings[0].rule == "http_status_below_500"
    assert result.findings[0].actual == "HTTP 500"


def test_browser_task_is_skipped_by_http_worker():
    worker = HTTPProbeWorker("http://localhost:5000")
    task = AgentTask(
        agent_id="agent_003",
        mode="browser",
        goal="Explore page in browser",
    )

    result = worker(task)

    assert result.status == "completed"
    assert result.findings == ()


def test_worker_rejects_invalid_path():
    worker = HTTPProbeWorker(
        "http://localhost:5000",
        paths=("https://example.com/",),
    )
    task = AgentTask(
        agent_id="agent_004",
        mode="http",
        goal="Check endpoint",
    )

    result = worker(task)

    assert result.status == "failed"
    assert "Only absolute local paths" in result.error