"""Human-readable and machine-readable report rendering.

Rendering is pure: the same :class:`StoredRun` always produces the same text, so
reports can be golden-tested.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from bugsafari.reporting.models import ActionRecord, Finding, RunStatus, StoredRun

STATUS_LABELS = {
    RunStatus.BUG_DETECTED: "BUG DETECTED",
    RunStatus.PASSED: "PASSED",
    RunStatus.EXECUTION_ERROR: "EXECUTION ERROR",
}


def reproduction_steps(finding: Finding) -> list[str]:
    """Format the recorded actions as concise reproduction instructions."""
    return [
        f"{index}. {action.action} {action.target}"
        + (f" = {action.value}" if action.value is not None else "")
        for index, action in enumerate(finding.reproduction_steps, start=1)
    ]


def render_markdown(run: StoredRun) -> str:
    """Render a complete, self-contained Markdown report."""
    lines: list[str] = [
        f"# BugSafari report — {run.run_id}",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Scenario | {_cell(run.scenario_name)} (`{run.scenario_id}`) |",
        f"| Status | **{STATUS_LABELS[run.status]}** |",
        f"| Started | {run.started_at} |",
        f"| Duration | {run.duration_s:.2f} s |",
        f"| Run id | `{run.run_id}` |",
        "",
    ]

    if run.error:
        lines += ["## Execution error", "", "```text", run.error, "```", ""]

    if run.findings:
        lines += ["## Findings", ""]
        for index, finding in enumerate(run.findings, start=1):
            lines += [
                f"### {index}. `{finding.rule}` ({finding.severity})",
                "",
                f"- **Expected:** {finding.expected}",
                f"- **Actual:** {finding.actual}",
                f"- **Status:** {finding.status}",
            ]
            if finding.details:
                lines.append(f"- **Details:** {finding.details}")
            lines += ["", "#### Reproduction steps", ""]
            steps = reproduction_steps(finding)
            lines += steps if steps else ["_No steps were recorded._"]
            lines.append("")
    elif run.status is RunStatus.PASSED:
        lines += ["## Result", "", "No invariant violation was found in this run.", ""]

    if run.minimized_actions is not None:
        reduction = len(run.actions) - len(run.minimized_actions)
        if reduction > 0:
            lines += [
                f"## Minimized reproduction ({len(run.actions)} → "
                f"{len(run.minimized_actions)} steps)",
                "",
            ]
            lines += _action_lines(run.minimized_actions)
        else:
            lines += [
                "## Minimized reproduction",
                "",
                "The recorded sequence was already minimal.",
                "",
            ]

    lines += [
        "## Action log",
        "",
        "| # | Action | Target | Value | Result |",
        "| --- | --- | --- | --- | --- |",
    ]
    for index, action in enumerate(run.actions, start=1):
        lines.append(
            f"| {index} | {_cell(action.action)} | `{_cell(action.target)}` | "
            f"{_cell(action.value or '')} | {_cell(action.result)} |"
        )
    lines.append("")

    if run.environment:
        lines += [
            "## Environment",
            "",
            "| Key | Value |",
            "| --- | --- |",
        ]
        for key in sorted(run.environment):
            lines.append(f"| {_cell(key)} | {_cell(run.environment[key])} |")
        lines.append("")

    lines += ["## Artifacts", "", "- `run.json`", "- `report.md`"]
    if run.screenshot:
        lines.append(f"- `{run.screenshot}`")
    if run.minimized_actions is not None:
        lines.append("- `minimized.json`")
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_json(run: StoredRun) -> str:
    """Serialize a run document for ``run.json``."""
    return json.dumps(run.to_dict(), indent=2, ensure_ascii=False) + "\n"


def summary_line(run: StoredRun) -> str:
    """One-line console summary used by the CLI."""
    detail = ""
    finding = run.primary_finding
    if finding is not None:
        detail = f"  {finding.rule}: expected {finding.expected}, actual {finding.actual}"
    elif run.error:
        detail = f"  {run.error.splitlines()[0]}"
    return f"{run.run_id}  {run.status.value:<15} {run.scenario_id}{detail}"


def _action_lines(actions: Sequence[ActionRecord]) -> list[str]:
    return [
        f"{index}. {action.action} {action.target}"
        + (f" = {action.value}" if action.value is not None else "")
        for index, action in enumerate(actions, start=1)
    ]


def _cell(value: str) -> str:
    """Keep table cells on one line."""
    return " ".join(str(value).split())
