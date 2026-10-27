
"""Streamlit dashboard for running and inspecting BugSafari."""

import json
import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bugsafari.config import load_settings
from bugsafari.engine.runner import run_scenario
from bugsafari.reporting.reporter import reproduction_steps
from bugsafari.scenarios.loader import ScenarioError, list_scenarios, load_scenario_by_id
from demo_app.app import create_app


# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="BugSafari | Browser Testing",
    page_icon="B",
    layout="wide",
)

st.title("BugSafari")
st.subheader("Autonomous Web Bug Detection")
st.write(
    "Explore a local web application, verify its behavior, "
    "and generate reproducible bug reports."
)
st.caption(
    "Current mode: Deterministic Playwright testing with explicit "
    "Python invariants. An LLM planner is not enabled in this run."
)

st.divider()

# ---------------------------------------------------------------------------
# Scenario selector
# ---------------------------------------------------------------------------

settings = load_settings()

try:
    available_scenarios = list_scenarios(settings.scenarios_dir)
except ScenarioError as exc:
    st.error(f"Could not load scenarios from `{settings.scenarios_dir}`:\n\n{exc}")
    st.stop()

if not available_scenarios:
    st.warning(
        f"No scenario files found in `{settings.scenarios_dir}`. "
        "Add a JSON scenario file and reload the page."
    )
    st.stop()

scenario_options = {s.id: s for s in available_scenarios}
scenario_labels = {
    s.id: f"{s.name} ({s.id})" for s in available_scenarios
}

selector_col, info_col = st.columns([1, 3])

with selector_col:
    selected_id = st.selectbox(
        "Select scenario",
        options=list(scenario_options.keys()),
        format_func=lambda sid: scenario_labels[sid],
        key="selected_scenario_id",
    )

selected_scenario = scenario_options[selected_id]

with info_col:
    st.info(selected_scenario.description)

run_col, _ = st.columns([1, 3])

with run_col:
    run_clicked = st.button(
        "Run Demo Test",
        type="primary",
        use_container_width=True,
    )

# ---------------------------------------------------------------------------
# Execute the selected scenario
# ---------------------------------------------------------------------------

if run_clicked:
    for key in (
        "run_result",
        "run_scenario_id",
        "replay_result",
        "replay_status",
        "dashboard_error",
    ):
        st.session_state.pop(key, None)

    with st.spinner("Running the scenario and verifying any detected bug..."):
        try:
            scenario = load_scenario_by_id(selected_id, settings.scenarios_dir)
            first_result = run_scenario(
                scenario, settings, app_factory=create_app
            )
            st.session_state["run_result"] = first_result
            st.session_state["run_scenario_id"] = selected_id

            if first_result.finding is not None:
                replay_result = run_scenario(
                    scenario, settings, app_factory=create_app
                )
                st.session_state["replay_result"] = replay_result

                if replay_result.status.value == "execution_error":
                    replay_status = "execution_error"
                elif replay_result.finding is None:
                    replay_status = "not_reproduced"
                elif (
                    replay_result.finding.signature()
                    == first_result.finding.signature()
                ):
                    replay_status = "confirmed"
                else:
                    replay_status = "different_finding"

                st.session_state["replay_status"] = replay_status

        except ScenarioError as exc:
            st.session_state["dashboard_error"] = (
                f"Scenario error: {exc}"
            )
        except Exception as exc:
            st.session_state["dashboard_error"] = (
                f"{type(exc).__name__}: {exc}"
            )


if st.session_state.get("dashboard_error"):
    st.error(
        "The test could not be completed:\n\n"
        + st.session_state["dashboard_error"]
    )


result = st.session_state.get("run_result")
run_scenario_id = st.session_state.get("run_scenario_id", selected_id)

if result is not None:
    st.divider()
    st.header("Test Results")

    replay_status = st.session_state.get("replay_status")

    if replay_status == "confirmed":
        st.success(
            "REPLAY VERIFIED: The same rule and expected/actual values "
            "were detected again."
        )
    elif replay_status == "not_reproduced":
        st.warning(
            "NOT REPRODUCED: The second run completed without detecting "
            "the original finding."
        )
    elif replay_status == "execution_error":
        replay_result = st.session_state.get("replay_result")
        st.error(
            "REPLAY EXECUTION ERROR: "
            + str(
                replay_result.error
                if replay_result is not None and replay_result.error
                else "Unknown replay error"
            )
        )
    elif replay_status == "different_finding":
        st.warning(
            "DIFFERENT FINDING: The replay's finding differs from "
            "the original."
        )

    if result.status.value == "bug_detected":
        st.success("BUG DETECTED: An invariant violation was confirmed.")
    elif result.status.value == "passed":
        st.success("TEST PASSED: All checked invariants were satisfied.")
    else:
        st.error(
            "EXECUTION ERROR: "
            + str(result.error or "Unknown error")
        )

    metric_columns = st.columns(3)

    with metric_columns[0]:
        st.metric(
            "Run Status",
            result.status.value.replace("_", " ").title(),
        )

    with metric_columns[1]:
        st.metric("Recorded Actions", len(result.actions))

    with metric_columns[2]:
        st.metric(
            "Finding",
            f"{len(result.findings)} detected" if result.findings else "None",
        )

    # Browser action log
    st.divider()
    st.header("Browser Action Log")

    if result.actions:
        st.table([
            {
                "Step": index,
                "Action": action.action,
                "Target": action.target,
                "Value": action.value if action.value is not None else "-",
                "Result": action.result,
            }
            for index, action in enumerate(result.actions, start=1)
        ])
    else:
        st.info("No browser actions were recorded.")

    # Bug report
    if result.findings:
        st.divider()
        st.header("Bug Reports")
        st.write(f"**Total findings:** {len(result.findings)}")

        for finding_index, finding in enumerate(result.findings, start=1):
            st.subheader(f"Finding {finding_index}: `{finding.rule}`")

        st.divider()
        st.header("Bug Report")
        st.write(f"**Violated rule:** `{finding.rule}`")
        st.write(f"**Summary:** {finding.details}")

        expected_column, actual_column = st.columns(2)

        with expected_column:
            st.metric("Expected Behavior", str(finding.expected))

        with actual_column:
            st.metric("Actual Behavior", str(finding.actual))

        st.subheader("Reproduction Steps")

        for step in reproduction_steps(finding):
            st.write(step)

        # Minimization results and diagnostics
        st.subheader("Reproduction Minimization")

        minimized_actions = result.minimized_actions
        stats = result.minimization_stats

        if stats is not None:
            metric_columns = st.columns(3)

            with metric_columns[0]:
                st.metric("Minimization Attempts", stats.get("attempts", 0))

            with metric_columns[1]:
                st.metric(
                    "Minimization Duration",
                    f"{stats.get('duration_s', 0)} s",
                )

            with metric_columns[2]:
                st.metric(
                    "Budget Exhausted",
                    "Yes" if stats.get("budget_exhausted") else "No",
                )

            st.write(
                f"Original scenario steps: "
                f"{stats.get('original_step_count', 'Unknown')}"
            )
            st.write(
                f"Candidate minimized steps: "
                f"{stats.get('minimized_step_count', 'Unknown')}"
            )

            if stats.get("same_finding_preserved") is True:
                st.success(
                    "The minimized sequence reproduced the same finding."
                )
            elif stats.get("same_finding_preserved") is False:
                st.warning(
                    "The candidate sequence did not preserve the original "
                    "finding, so it was not accepted."
                )
            elif stats.get("changed") is False:
                st.info(
                    "No shorter sequence was found. The original sequence "
                    "still reproduces the finding."
                )

        if minimized_actions is not None:
            st.write("**Verified minimized action sequence**")

            st.table([
                {
                    "Step": index,
                    "Action": action.action,
                    "Target": action.target,
                    "Value": action.value if action.value is not None else "-",
                    "Result": action.result,
                }
                for index, action in enumerate(
                    minimized_actions,
                    start=1,
                )
            ])
        elif stats is None:
            st.info(
                "Minimization was not run for this result, or its "
                "statistics are unavailable."
            )
        elif stats.get("changed") is False:
            st.info(
                "No shorter sequence was returned. This can be expected "
                "when every original action is necessary."
            )
        else:
            st.info(
                "No verified shorter sequence is available. Check the "
                "minimization diagnostics above."
            )

        st.subheader("Suggested Investigation")
        if finding.details:
            st.write(finding.details)
        else:
            st.write(
                "Review the failing invariant rule and the browser action log "
                "to identify which cart update did not recalculate the totals."
            )

        with st.expander("Technical finding details"):
            st.write("**Rule identifier**")
            st.code(str(finding.rule))
            st.write("**Expected**")
            st.code(str(finding.expected))
            st.write("**Actual**")
            st.code(str(finding.actual))
            st.write("**Details**")
            st.text(str(finding.details))

    elif result.status.value == "passed":
        st.info("No invariant violation was found during this run.")

    # Screenshot evidence
    st.divider()
    st.header("Screenshot Evidence")

    if result.screenshot:
        screenshot_path = Path(result.screenshot)

        if screenshot_path.is_file():
            st.image(
                str(screenshot_path),
                caption="Browser state captured during the test run",
                use_container_width=True,
            )
        else:
            st.warning("The screenshot file could not be found.")
            st.code(str(result.screenshot))
    else:
        st.info("No screenshot is available for this run.")

    # JSON bug report
    if result.findings:
        finding = result.finding
        replay_result = st.session_state.get("replay_result")
        minimized_actions = result.minimized_actions

        report_data = {
            "project": "BugSafari",
            "run_id": result.run_id,
            "scenario": run_scenario_id,
            "detection": {
                "status": result.status.value,
                "rule": finding.rule,
                "severity": finding.severity,
                "expected": finding.expected,
                "actual": finding.actual,
                "details": finding.details,
            },
            "findings": [
    {
        "rule": item.rule,
        "severity": item.severity,
        "status": item.status,
        "expected": item.expected,
        "actual": item.actual,
        "details": item.details,
        "reproduction_steps": [
            {
                "action": action.action,
                "target": action.target,
                "value": action.value,
                "result": action.result,
            }
            for action in item.reproduction_steps
        ],
    }
    for item in result.findings
],
            "replay_verification": {
                "status": st.session_state.get("replay_status", "not_run"),
                "run_id": (
                    replay_result.run_id
                    if replay_result is not None
                    else None
                ),
                "error": (
                    replay_result.error
                    if replay_result is not None
                    else None
                ),
            },
            "browser_actions": [
                {
                    "step": index,
                    "action": action.action,
                    "target": action.target,
                    "value": action.value,
                    "result": action.result,
                }
                for index, action in enumerate(result.actions, start=1)
            ],
            "reproduction_steps": [
                {
                    "action": action.action,
                    "target": action.target,
                    "value": action.value,
                    "result": action.result,
                }
                for action in finding.reproduction_steps
            ],
            "minimization": {
                "available": minimized_actions is not None,
                "stats": result.minimization_stats,
                "actions": (
                    [
                        {
                            "step": index,
                            "action": action.action,
                            "target": action.target,
                            "value": action.value,
                            "result": action.result,
                        }
                        for index, action in enumerate(
                            minimized_actions,
                            start=1,
                        )
                    ]
                    if minimized_actions is not None
                    else None
                ),
            },
            "screenshot": result.screenshot,
        }

        report_json = json.dumps(
            report_data,
            indent=2,
            ensure_ascii=False,
        )

        st.divider()
        st.header("Export Bug Report")

        st.download_button(
            label="Download Bug Report (JSON)",
            data=report_json,
            file_name=f"bugsafari-report-{result.run_id or 'latest'}.json",
            mime="application/json",
            type="primary",
        )

        with st.expander("Preview JSON report"):
            st.code(report_json, language="json")


st.divider()
st.caption("BugSafari | Local browser testing and reproducible bug reports")
