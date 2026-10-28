"""Human-readable and machine-readable report rendering.

Rendering is pure: the same :class:`StoredRun` always produces the same text, so
reports can be golden-tested.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from html import escape

from bugsafari.reporting.models import ActionRecord, Finding, RunStatus, StoredRun

STATUS_LABELS = {
    RunStatus.BUG_DETECTED: "BUG DETECTED",
    RunStatus.PASSED: "PASSED",
    RunStatus.EXECUTION_ERROR: "EXECUTION ERROR",
}


def reproduction_steps(finding: Finding) -> list[str]:
    """Format the recorded actions as concise reproduction instructions."""
    return [
        f"{index}. {_action_text(action)}"
        for index, action in enumerate(finding.reproduction_steps, start=1)
    ]


def _action_text(action: ActionRecord) -> str:
    return f"{action.action} {action.target}" + (
        f" = {action.value}" if action.value is not None else ""
    )


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
                f"### {index}. [{finding.severity.upper()}] {finding.category}: "
                f"{finding.title or finding.rule} (`{finding.rule}`)",
                "",
                f"- **Location:** `{finding.selector or 'not captured'}` on "
                f"{finding.page_url or 'unknown page'}"
                + (
                    f" at {finding.viewport['width']}×{finding.viewport['height']} px"
                    if "width" in finding.viewport and "height" in finding.viewport
                    else ""
                ),
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
    if run.minimized_actions is not None:
        lines.append("- `minimized.json`")
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_json(run: StoredRun) -> str:
    """Serialize a run document for ``run.json``."""
    return json.dumps(run.to_dict(), indent=2, ensure_ascii=False) + "\n"


def render_html(run: StoredRun) -> str:
    """Render a self-contained text-only HTML report without embedded images."""
    parts = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>BugSafari report {escape(run.run_id)}</title>",
        "<style>body{font:16px system-ui,sans-serif;max-width:960px;"
        "margin:2rem auto;padding:0 1rem}"
        ".finding{border:1px solid #aaa;border-left-width:6px;padding:1rem;margin:1rem 0}"
        ".critical{border-left-color:#b42318}.high{border-left-color:#c2410c}"
        ".medium{border-left-color:#a16207}.low{border-left-color:#2563eb}"
        "dt{font-weight:700}dd{margin:0 0 .6rem}</style></head><body>",
        f"<h1>BugSafari report — {escape(run.run_id)}</h1>",
        f"<p>Status: <strong>{escape(STATUS_LABELS[run.status])}</strong>; "
        f"Scenario: {escape(run.scenario_name)} ({escape(run.scenario_id)})</p>",
    ]
    if run.error:
        parts.append(f"<p><strong>Execution error:</strong> {escape(run.error)}</p>")
    for finding in run.findings:
        severity_class = finding.severity.lower()
        parts.extend(
            [
                f'<article class="finding {escape(severity_class)}">',
                f"<h2>[{escape(finding.severity.upper())}] {escape(finding.category)} — "
                f"{escape(finding.title or finding.rule)}</h2>",
                f"<p>Rule: <code>{escape(finding.rule)}</code></p>",
                "<dl>",
                f"<dt>Expected</dt><dd>{escape(finding.expected)}</dd>",
                f"<dt>Observed</dt><dd>{escape(finding.actual)}</dd>",
                "<dt>Selector</dt><dd><code>"
                f"{escape(finding.selector or 'not captured')}</code></dd>",
                f"<dt>Page</dt><dd>{escape(finding.page_url or 'unknown page')}</dd>",
                "<dt>Viewport</dt><dd>"
                f"{escape(str(finding.viewport) if finding.viewport else 'not captured')}</dd>",
                "</dl>",
                "<h3>Discovery path</h3><ol>",
            ]
        )
        for action in finding.reproduction_steps:
            parts.append(f"<li>{escape(_action_text(action))}</li>")
        if not finding.reproduction_steps:
            parts.append("<li>No steps were recorded.</li>")
        parts.append("</ol></article>")
    parts.append("</body></html>")
    return "\n".join(parts)


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
