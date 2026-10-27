
"""Bounded multi-agent orchestration for BugSafari.

This module is independent of the existing browser runner so the current
deterministic tests and dashboard remain unchanged.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from threading import Lock
from typing import Callable, Literal


AgentMode = Literal["browser", "http"]
AgentStatus = Literal["completed", "failed"]


@dataclass(frozen=True)
class AgentTask:
    """Work assigned to one logical simulated user."""

    agent_id: str
    mode: AgentMode
    goal: str
    scenario_id: str | None = None


@dataclass(frozen=True)
class FindingReport:
    """A structured bug candidate reported by an agent."""

    title: str
    target: str
    rule: str
    expected: str
    actual: str
    reproduction_steps: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    suggested_fix: str = ""

    @property
    def deduplication_key(self) -> tuple[str, str, str]:
        """Normalize equivalent findings to help group duplicate reports."""
        return (
            self.target.strip().casefold(),
            self.rule.strip().casefold(),
            self.title.strip().casefold(),
        )


@dataclass(frozen=True)
class AgentResult:
    """Result returned by a worker after processing one task."""

    agent_id: str
    status: AgentStatus
    findings: tuple[FindingReport, ...] = ()
    error: str | None = None


@dataclass
class MultiAgentReport:
    """Summary produced by the coordinator."""

    requested_agents: int
    completed_agents: int = 0
    failed_agents: int = 0
    verified_findings: list[FindingReport] = field(default_factory=list)
    rejected_findings: int = 0
    duplicate_findings: int = 0
    agent_results: list[AgentResult] = field(default_factory=list)


AgentWorker = Callable[[AgentTask], AgentResult]
FindingVerifier = Callable[[FindingReport], bool]


class MultiAgentCoordinator:
    """Run logical agents concurrently with a strict worker limit."""

    def __init__(
        self,
        max_concurrency: int = 10,
        verifier: FindingVerifier | None = None,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")

        self.max_concurrency = max_concurrency
        # Without a real verifier, findings remain unverified and are not
        # presented as confirmed bugs.
        self.verifier = verifier

    def run(
        self,
        tasks: list[AgentTask],
        worker: AgentWorker,
    ) -> MultiAgentReport:
        """Execute tasks and aggregate verified, deduplicated findings."""
        agent_ids = [task.agent_id for task in tasks]
        if len(agent_ids) != len(set(agent_ids)):
            raise ValueError("Every agent must have a unique agent_id")

        report = MultiAgentReport(requested_agents=len(tasks))
        if not tasks:
            return report

        with ThreadPoolExecutor(
            max_workers=self.max_concurrency,
            thread_name_prefix="bugsafari-agent",
        ) as executor:
            future_to_task = {
                executor.submit(worker, task): task for task in tasks
            }

            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    if result.agent_id != task.agent_id:
                        result = AgentResult(
                            agent_id=task.agent_id,
                            status="failed",
                            error="Worker returned a mismatched agent_id",
                        )
                except Exception as exc:
                    result = AgentResult(
                        agent_id=task.agent_id,
                        status="failed",
                        error=f"{type(exc).__name__}: {exc}",
                    )

                report.agent_results.append(result)
                if result.status == "failed":
                    report.failed_agents += 1
                    continue

                report.completed_agents += 1

                for finding in result.findings:
                    if self.verifier is None:
                        report.rejected_findings += 1
                        continue

                    try:
                        verified = self.verifier(finding)
                    except Exception:
                        verified = False

                    if not verified:
                        report.rejected_findings += 1
                        continue

                    key = finding.deduplication_key
                    existing_keys = {
                        item.deduplication_key
                        for item in report.verified_findings
                    }
                    if key in existing_keys:
                        report.duplicate_findings += 1
                    else:
                        report.verified_findings.append(finding)

        report.agent_results.sort(key=lambda item: item.agent_id)
        report.verified_findings.sort(key=lambda item: item.deduplication_key)
        return report


def create_agent_tasks(
    count: int = 100,
    *,
    browser_ratio: float = 0.5,
    scenario_id: str | None = None,
) -> list[AgentTask]:
    """Create logical user tasks split between browser and HTTP strategies.

    This creates task definitions, not 100 running browser instances or
    real HTTP traffic. The worker determines how each task is executed.
    """
    if count < 0:
        raise ValueError("count cannot be negative")
    if not 0.0 <= browser_ratio <= 1.0:
        raise ValueError("browser_ratio must be between 0.0 and 1.0")

    browser_count = round(count * browser_ratio)
    tasks: list[AgentTask] = []

    for index in range(count):
        mode: AgentMode = (
            "browser" if index < browser_count else "http"
        )
        goal = (
            "Explore user-visible controls and validate page behavior"
            if mode == "browser"
            else "Check HTTP responses, latency, and request failures"
        )
        tasks.append(
            AgentTask(
                agent_id=f"agent_{index + 1:03d}",
                mode=mode,
                goal=goal,
                scenario_id=scenario_id,
            )
        )

    return tasks
