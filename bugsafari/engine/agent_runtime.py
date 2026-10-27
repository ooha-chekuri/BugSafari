
"""Connect browser and HTTP workers to the multi-agent coordinator."""
from __future__ import annotations

from pathlib import Path

from bugsafari.engine.agent_worker import HTTPProbeWorker
from bugsafari.engine.browser_agent_worker import BrowserAgentWorker
from bugsafari.engine.multi_agent import (
    AgentResult,
    AgentTask,
    FindingVerifier,
    MultiAgentCoordinator,
    MultiAgentReport,
    create_agent_tasks,
)


class CombinedAgentWorker:
    """Dispatch each task to the worker matching its mode."""

    def __init__(
        self,
        http_worker: HTTPProbeWorker,
        browser_worker: BrowserAgentWorker,
    ) -> None:
        self.http_worker = http_worker
        self.browser_worker = browser_worker

    def __call__(self, task: AgentTask) -> AgentResult:
        if task.mode == "http":
            return self.http_worker(task)

        if task.mode == "browser":
            return self.browser_worker(task)

        return AgentResult(
            agent_id=task.agent_id,
            status="failed",
            error=f"Unsupported agent mode: {task.mode}",
        )


def run_agents(
    base_url: str,
    *,
    count: int = 5,
    browser_ratio: float = 0.5,
    max_concurrency: int = 3,
    paths: tuple[str, ...] = ("/",),
    timeout_seconds: float = 3.0,
    browser_timeout_ms: int = 5000,
    artifact_dir: str | Path = "artifacts/browser_agents",
    scenario_id: str | None = None,
    verifier: FindingVerifier | None = None,
) -> MultiAgentReport:
    """Run browser and HTTP agents against a configured local target.

    Findings remain unverified unless a verifier is explicitly supplied.
    """
    if count < 0:
        raise ValueError("count cannot be negative")

    tasks = create_agent_tasks(
        count=count,
        browser_ratio=browser_ratio,
        scenario_id=scenario_id,
    )

    http_worker = HTTPProbeWorker(
        base_url=base_url,
        paths=paths,
        timeout_seconds=timeout_seconds,
    )
    browser_worker = BrowserAgentWorker(
        base_url=base_url,
        timeout_ms=browser_timeout_ms,
        artifact_dir=artifact_dir,
    )

    worker = CombinedAgentWorker(
        http_worker=http_worker,
        browser_worker=browser_worker,
    )

    coordinator = MultiAgentCoordinator(
        max_concurrency=max_concurrency,
        verifier=verifier,
    )
    return coordinator.run(tasks, worker)


def run_http_agents(
    base_url: str,
    *,
    count: int = 5,
    max_concurrency: int = 3,
    paths: tuple[str, ...] = ("/",),
    timeout_seconds: float = 3.0,
    verifier: FindingVerifier | None = None,
) -> MultiAgentReport:
    """Preserve the existing HTTP-only runtime interface."""
    return run_agents(
        base_url,
        count=count,
        browser_ratio=0.0,
        max_concurrency=max_concurrency,
        paths=paths,
        timeout_seconds=timeout_seconds,
        verifier=verifier,
    )
