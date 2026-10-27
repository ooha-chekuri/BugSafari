
from threading import Lock
from time import sleep

from bugsafari.engine.multi_agent import (
    AgentResult,
    AgentTask,
    FindingReport,
    MultiAgentCoordinator,
    create_agent_tasks,
)


def test_creates_100_logical_agents():
    tasks = create_agent_tasks(100)

    assert len(tasks) == 100
    assert len({task.agent_id for task in tasks}) == 100
    assert sum(task.mode == "browser" for task in tasks) == 50
    assert sum(task.mode == "http" for task in tasks) == 50


def test_agent_concurrency_is_bounded():
    tasks = create_agent_tasks(20)
    lock = Lock()
    active = 0
    peak_active = 0

    def worker(task):
        nonlocal active, peak_active

        with lock:
            active += 1
            peak_active = max(peak_active, active)

        try:
            sleep(0.02)
            return AgentResult(
                agent_id=task.agent_id,
                status="completed",
            )
        finally:
            with lock:
                active -= 1

    report = MultiAgentCoordinator(max_concurrency=3).run(tasks, worker)

    assert report.completed_agents == 20
    assert report.failed_agents == 0
    assert peak_active <= 3


def test_duplicate_verified_findings_are_grouped():
    finding = FindingReport(
        title="Cart total mismatch",
        target="demo-shop",
        rule="cart_total_matches_quantities",
        expected="$36.00",
        actual="$18.00",
    )

    tasks = [
        AgentTask("agent_001", "browser", "Test cart"),
        AgentTask("agent_002", "http", "Check API"),
    ]

    def worker(task):
        return AgentResult(
            agent_id=task.agent_id,
            status="completed",
            findings=(finding,),
        )

    report = MultiAgentCoordinator(
        max_concurrency=2,
        verifier=lambda item: True,
    ).run(tasks, worker)

    assert len(report.verified_findings) == 1
    assert report.duplicate_findings == 1


def test_findings_are_not_confirmed_without_verifier():
    finding = FindingReport(
        title="Possible issue",
        target="demo-shop",
        rule="example_rule",
        expected="expected",
        actual="actual",
    )
    task = AgentTask("agent_001", "browser", "Explore")

    report = MultiAgentCoordinator().run(
        [task],
        lambda item: AgentResult(
            agent_id=item.agent_id,
            status="completed",
            findings=(finding,),
        ),
    )

    assert report.verified_findings == []
    assert report.rejected_findings == 1
