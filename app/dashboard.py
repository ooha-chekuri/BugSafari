"""Streamlit dashboard for running and inspecting a real browser exploration."""

import sys
from pathlib import Path

import streamlit as st

# Streamlit may put only this script's ``app/`` directory on sys.path when
# launched with ``streamlit run app/dashboard.py``. Add the project root so
# the sibling ``bugsafari`` and ``demo_app`` packages remain importable.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bugsafari.engine.explorer import run_demo_exploration
from bugsafari.reporting.reporter import reproduction_steps


st.set_page_config(page_title="BugSafari", page_icon="🐞", layout="centered")
st.title("🐞 BugSafari")
st.write("A deterministic browser test explores the local shop and checks its cart total invariant.")
st.caption("This run uses a fixed action sequence and explicit Python checks. It does not use an LLM.")

if st.button("Run demo test", type="primary"):
    with st.spinner("Starting the demo shop and running Playwright…"):
        st.session_state["run_result"] = run_demo_exploration()

result = st.session_state.get("run_result")
if result:
    if result.status == "bug_detected":
        st.success("BugSafari run completed: seeded bug detected.")
    elif result.status == "passed":
        st.success("BugSafari run completed: checked invariant passed.")
    else:
        st.error(f"Browser or test execution error: {result.error or 'Unknown error'}")

    st.subheader("Action log")
    if result.actions:
        st.dataframe([{"Action": a.action, "Target": a.target, "Value": a.value or "", "Result": a.result}
                      for a in result.actions], use_container_width=True, hide_index=True)
    else:
        st.info("No actions were completed.")

    if result.finding:
        finding = result.finding
        st.subheader("Bug report")
        st.write(f"**Violated rule:** `{finding.rule}`")
        st.write(f"**Expected:** {finding.expected}  ·  **Actual:** {finding.actual}")
        st.write(finding.details)
        st.write("**Reproduction steps**")
        for step in reproduction_steps(finding):
            st.write(step)
    elif result.status == "passed":
        st.info("No invariant violation was found in this run.")

    st.subheader("Screenshot")
    if result.screenshot:
        st.image(result.screenshot, caption="Browser state after the test sequence")
    else:
        st.info("No screenshot is available because the browser did not reach the capture step.")
