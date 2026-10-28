"""Streamlit dashboard for running and inspecting BugSafari."""

import json
import sys
from html import escape
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bugsafari.config import load_settings
from bugsafari.engine.runner import run_scenario
from bugsafari.reporting.reporter import render_html, reproduction_steps
from bugsafari.reporting.store import RunStore
from bugsafari.scenarios.loader import ScenarioError, list_scenarios, load_scenario_by_id
from bugsafari.scenarios.website_scan import website_scan_scenario
from demo_app.app import create_app


# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="BugSafari",
    page_icon="\U0001F41E",
    layout="wide",
)


def inject_css() -> None:
    """Apply the Digital Safari theme and small, responsive UI animations."""
    st.markdown(
        """
        <style>
          @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');
          :root {
            --safari-bg:rgb(16, 26, 21); --safari-panel:rgb(31 48 39 / 92%); --safari-panel-soft:rgb(43 61 49 / 82%);
            --safari-ink:rgb(248, 246, 237); --safari-muted:rgb(207, 216, 202); --safari-line:rgb(214 224 198 / 22%);
            --safari-green:rgb(36, 75, 56); --safari-sand:rgb(232, 214, 174); --safari-amber:rgb(221, 168, 90);
            --safari-firefly:rgb(214, 255, 114); --safari-shadow:rgb(0 0 0 / 38%);
          }
          html { scroll-behavior:smooth; }
          .stApp { color:var(--safari-ink); background:radial-gradient(ellipse at 12% 0%,rgb(36, 62, 47) 0,transparent 42%),radial-gradient(ellipse at 95% 34%,rgb(48, 43, 28) 0,transparent 32%),var(--safari-bg); font-family:Inter,system-ui,sans-serif; }
          [data-testid="stHeader"] { background:rgb(16 26 21 / 75%); }
          [data-testid="stMainBlockContainer"] { max-width:1320px; padding-top:1.5rem; }
          h1,h2,h3,h4 { color:var(--safari-ink); font-family:'Space Grotesk',Inter,sans-serif; letter-spacing:-.035em; }
          p,li,label,[data-testid="stCaptionContainer"] { color:var(--safari-muted); }
          .safari-hero { position:relative; overflow:hidden; isolation:isolate; padding:clamp(2rem,5vw,4rem); margin:.25rem 0 1.6rem; border:1px solid rgb(226 237 206 / 25%); border-radius:28px; background:linear-gradient(115deg,rgb(24 55 39 / 98%),rgb(42 51 35 / 92%) 58%,rgb(84 61 32 / 85%)); box-shadow:0 22px 70px var(--safari-shadow); animation:safari-arrive .65s ease both; }
          .safari-hero::before { content:""; position:absolute; z-index:-1; inset:-80%; opacity:.36; background:conic-gradient(from 90deg,transparent,rgb(143,174,86),transparent,rgb(209,154,79),transparent); animation:safari-drift 22s linear infinite; }
          .safari-hero::after { content:""; position:absolute; z-index:-1; inset:1px; border-radius:27px; background:linear-gradient(115deg,rgb(24 55 39 / 98%),rgb(35 47 35 / 96%) 60%,rgb(70 53 32 / 93%)); }
          .safari-eyebrow { font:700 .72rem/1.4 Inter,sans-serif; letter-spacing:.18em; text-transform:uppercase; color:var(--safari-firefly); }
          .safari-hero h1 { margin:.65rem 0 .35rem; font-size:clamp(2.6rem,7vw,5.4rem); line-height:.98; background:linear-gradient(100deg,rgb(255,248,232) 7%,rgb(232,214,174) 47%,rgb(214,255,114) 92%); -webkit-background-clip:text; background-clip:text; color:transparent; }
          .safari-hero p { max-width:690px; margin:0; font-size:clamp(1rem,2vw,1.18rem); }
          .safari-section { margin:1.35rem 0 .6rem; animation:safari-arrive .5s ease both; }
          div[data-testid="stVerticalBlockBorderWrapper"] { border:1px solid var(--safari-line); border-radius:20px; background:var(--safari-panel); box-shadow:0 14px 42px var(--safari-shadow); backdrop-filter:blur(16px); transition:transform .2s ease,border-color .2s ease,box-shadow .2s ease; animation:safari-arrive .5s ease both; }
          @media (hover:hover) and (pointer:fine) { div[data-testid="stVerticalBlockBorderWrapper"]:hover { border-color:rgb(214 255 114 / 45%); box-shadow:0 18px 50px rgb(0 0 0 / 42%),0 0 24px rgb(214 255 114 / 10%); } }
          div.stButton > button, [data-testid="stDownloadButton"] button { min-height:2.8rem; border:1px solid rgb(214 255 114 / 55%); border-radius:13px; color:rgb(24,35,24); background:linear-gradient(115deg,rgb(214,255,114),rgb(180,217,92) 65%,rgb(237,193,110)); font-weight:750; box-shadow:0 8px 26px rgb(160 211 76 / 25%); transition:transform .18s ease,box-shadow .18s ease,filter .18s ease; }
          div.stButton > button, div.stButton > button *, [data-testid="stDownloadButton"] button, [data-testid="stDownloadButton"] button * { color:rgb(0,0,0)!important; }
          div.stButton > button:hover, [data-testid="stDownloadButton"] button:hover { color:rgb(20,32,23); border-color:rgb(237,255,182); filter:brightness(1.06); transform:translateY(-2px); box-shadow:0 12px 30px rgb(160 211 76 / 34%); }
          div.stButton > button:focus-visible,button:focus-visible,input:focus-visible,textarea:focus-visible { outline:3px solid var(--safari-firefly)!important; outline-offset:3px!important; }
          input,textarea,[data-baseweb="select"] > div { color:var(--safari-ink)!important; border-color:var(--safari-line)!important; border-radius:12px!important; background:rgb(12 22 17 / 92%)!important; }
          [data-baseweb="radio"] label { color:var(--safari-ink); }
          [data-baseweb="tab-list"] { gap:.45rem; border-bottom:1px solid var(--safari-line); }
          [data-baseweb="tab"] { border-radius:11px 11px 0 0; color:var(--safari-muted); }
          [aria-selected="true"][data-baseweb="tab"] { color:var(--safari-firefly)!important; }
          [data-testid="stSidebar"] { background:rgb(12 22 17 / 94%); border-right:1px solid var(--safari-line); backdrop-filter:blur(18px); }
          [data-testid="stSidebar"] * { color:var(--safari-ink); }
          [data-testid="stMetric"] { padding:1rem 1.15rem; border:1px solid var(--safari-line); border-radius:17px; background:linear-gradient(145deg,rgb(39 61 47 / 96%),rgb(24 38 30 / 96%)); box-shadow:0 8px 28px var(--safari-shadow),inset 0 1px rgb(255 255 255 / 6%); }
          [data-testid="stMetricLabel"] { color:var(--safari-muted); }
          [data-testid="stMetricValue"] { color:var(--safari-firefly); font-family:'Space Grotesk',sans-serif; text-shadow:0 0 20px rgb(214 255 114 / 25%); }
          [data-testid="stDataFrame"],[data-testid="stTable"] { border:1px solid var(--safari-line); border-radius:15px; overflow:hidden; background:var(--safari-panel); color:var(--safari-ink); color-scheme:dark; }
          [role="listbox"],[role="option"] { color:var(--safari-ink); background:rgb(20 32 25); }
          .finding-card { padding:.2rem .15rem .35rem; border-left:3px solid var(--safari-firefly); }
          .finding-card.severity-critical { border-color:rgb(255,107,98); }
          .finding-card.severity-high { border-color:rgb(243,163,92); }
          .finding-card.severity-medium { border-color:rgb(233,204,103); }
          .finding-card.severity-low { border-color:rgb(119,198,220); }
          .finding-eyebrow { color:var(--safari-firefly); font-size:.7rem; font-weight:750; letter-spacing:.1em; text-transform:uppercase; }
          .finding-card h3 { margin:.45rem 0; }
          .finding-card p { color:var(--safari-muted); }
          [data-testid="stExpander"] { border:1px solid var(--safari-line); border-radius:15px; background:rgb(31 48 39 / 90%); }
          [data-testid="stAlert"] { border:1px solid var(--safari-line); border-radius:14px; background:rgb(32 49 39 / 96%); color:var(--safari-ink); }
          [data-testid="stSpinner"] > div { border-top-color:var(--safari-firefly)!important; }
          [data-testid="stSuccess"] { border:1px solid rgb(214 255 114 / 48%); box-shadow:0 0 24px rgb(214 255 114 / 12%); }
          #MainMenu,footer { visibility:hidden; }
          @keyframes safari-drift { to { transform:rotate(360deg); } }
          @keyframes safari-arrive { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:translateY(0); } }
          @media(max-width:720px) { [data-testid="stMainBlockContainer"] { padding:1rem .8rem 2rem; } .safari-hero { border-radius:20px; } }
          @media(prefers-reduced-motion:reduce) { *,*::before,*::after { animation-duration:.01ms!important; animation-iteration-count:1!important; scroll-behavior:auto!important; transition-duration:.01ms!important; } }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_css()

settings = load_settings()
st.markdown(
    """
    <section class="safari-hero">
      <div class="safari-eyebrow">BUGSAFARI / WEBSITE FIELD GUIDE</div>
      <h1>BugSafari</h1>
      <p>A field guide for spotting real website issues.</p>
    </section>
    """,
    unsafe_allow_html=True,
)

st.divider()

# ---------------------------------------------------------------------------
# Scan setup
# ---------------------------------------------------------------------------

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
scenario_labels = {s.id: f"{s.name} ({s.id})" for s in available_scenarios}

st.header("Test target")
selected_id: str | None = None
website_url = ""
with st.container(border=True):
    testing_mode = st.radio(
        "Test target",
        options=("Website URL", "Bundled demo scenario"),
        horizontal=True,
        label_visibility="collapsed",
    )
    if testing_mode == "Website URL":
        website_url = st.text_input(
            "Website URL",
            value=settings.target_url or "",
            placeholder="https://www.example.com",
            help=(
                "Scans the loaded page at responsive widths. It does not submit "
                "forms or crawl links."
            ),
        )
        st.caption("Read-only page scan | Responsive layout | Image checks | Accessibility checks")
        run_label = "Scan Website"
    else:
        selector_col, info_col = st.columns([1, 2])
        with selector_col:
            selected_id = st.selectbox(
                "Select demo scenario",
                options=list(scenario_options.keys()),
                format_func=lambda sid: scenario_labels[sid],
                key="selected_scenario_id",
            )
        with info_col:
            st.markdown("### Bundled demo")
            st.caption(scenario_options[selected_id].description)
        run_label = "Run Demo Scenario"

    run_col, _ = st.columns([1, 3])
    with run_col:
        run_clicked = st.button(run_label, type="primary", use_container_width=True)

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
            if testing_mode == "Website URL":
                scenario = website_scan_scenario(website_url)
            else:
                scenario = load_scenario_by_id(selected_id, settings.scenarios_dir)
            first_result = run_scenario(scenario, settings, app_factory=create_app)
            st.session_state["run_result"] = first_result
            st.session_state["run_scenario_id"] = scenario.id

            if first_result.finding is not None:
                replay_result = run_scenario(scenario, settings, app_factory=create_app)
                st.session_state["replay_result"] = replay_result

                if replay_result.status.value == "execution_error":
                    replay_status = "execution_error"
                elif replay_result.finding is None:
                    replay_status = "not_reproduced"
                elif replay_result.finding.signature() == first_result.finding.signature():
                    replay_status = "confirmed"
                else:
                    replay_status = "different_finding"

                st.session_state["replay_status"] = replay_status

        except ScenarioError as exc:
            st.session_state["dashboard_error"] = f"Scenario error: {exc}"
        except Exception as exc:
            st.session_state["dashboard_error"] = f"{type(exc).__name__}: {exc}"


if st.session_state.get("dashboard_error"):
    st.error("The test could not be completed:\n\n" + st.session_state["dashboard_error"])


result = st.session_state.get("run_result")
run_scenario_id = st.session_state.get("run_scenario_id", selected_id)

if result is not None:
    st.divider()
    st.header("Scan Results")

    replay_status = st.session_state.get("replay_status")

    if replay_status == "confirmed":
        st.success("REPLAY VERIFIED: The same rule and expected/actual values were detected again.")
    elif replay_status == "not_reproduced":
        st.warning(
            "NOT REPRODUCED: The second run completed without detecting the original finding."
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
        st.warning("DIFFERENT FINDING: The replay's finding differs from the original.")

    if result.status.value == "bug_detected":
        st.success("CHECKS FLAGGED AN ISSUE: Review the findings below.")
    elif result.status.value == "passed":
        st.success("TEST PASSED: All checked invariants were satisfied.")
    else:
        st.error("EXECUTION ERROR: " + str(result.error or "Unknown error"))

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
            "Findings",
            f"{len(result.findings)} detected" if result.findings else "None",
        )

    # Browser action log
    st.divider()
    st.header("Browser Action Log")

    if result.actions:
        st.dataframe(
            [
                {
                    "Step": index,
                    "Action": action.action,
                    "Target": action.target,
                    "Value": action.value if action.value is not None else "-",
                    "Result": action.result,
                }
                for index, action in enumerate(result.actions, start=1)
            ],
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("No browser actions were recorded.")

    # Bug report
    if result.findings:
        st.divider()
        st.header(
            f"{len(result.findings)} issue{'s' if len(result.findings) != 1 else ''} to review"
        )
        for finding in result.findings:
            severity = finding.severity.lower()
            with st.container(border=True):
                st.markdown(
                    f'<div class="finding-card severity-{severity}">'
                    f'<div class="finding-eyebrow">* {escape(finding.severity.upper())} - {escape(finding.category)}</div>'
                    f'<h3>{escape(finding.title or finding.rule)}</h3>'
                    f'<p>{escape(finding.details)}</p>'
                    f'<small>Rule: {escape(finding.rule)}</small></div>',
                    unsafe_allow_html=True,
                )
            location = finding.selector or "Location not captured"
            if len(location) > 112:
                location = f"{location[:52]} ... {location[-52:]}"
            page_url = finding.page_url or "Page not captured"
            viewport = (
                f"{finding.viewport['width']} x {finding.viewport['height']} px"
                if "width" in finding.viewport and "height" in finding.viewport
                else "Viewport not captured"
            )
            st.caption(f"{location}  |  {page_url}  |  {viewport}")

        finding = result.finding or result.findings[0]
        expected_column, actual_column = st.columns(2)
        with expected_column:
            st.metric("Expected", str(finding.expected))
        with actual_column:
            st.metric("Observed", str(finding.actual))

        st.subheader("Primary Reproduction Path")

        for step in reproduction_steps(finding):
            st.write(step)

        # Minimization results and diagnostics
        st.subheader("Path Minimization")

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

            st.write(f"Original scenario steps: {stats.get('original_step_count', 'Unknown')}")
            st.write(f"Candidate minimized steps: {stats.get('minimized_step_count', 'Unknown')}")

            if stats.get("same_finding_preserved") is True:
                st.success("The minimized sequence reproduced the same finding.")
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

            st.dataframe(
                [
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
                ],
                hide_index=True,
                use_container_width=True,
            )
        elif stats is None:
            st.info("Minimization was not run for this result, or its statistics are unavailable.")
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
        st.info("No issues were detected by the selected checks on this page.")

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
                "title": finding.title or finding.rule,
                "category": finding.category,
                "severity": finding.severity,
                "expected": finding.expected,
                "actual": finding.actual,
                "details": finding.details,
                "selector": finding.selector,
                "page_url": finding.page_url,
                "viewport": finding.viewport,
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
                "run_id": (replay_result.run_id if replay_result is not None else None),
                "error": (replay_result.error if replay_result is not None else None),
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
        }

        report_json = json.dumps(
            report_data,
            indent=2,
            ensure_ascii=False,
        )

        st.divider()
        st.header("Export Bug Report")

        json_tab, html_tab = st.tabs(["JSON report", "HTML report"])
        with json_tab:
            st.download_button(
                label="Download Bug Report (JSON)",
                data=report_json,
                file_name=f"bugsafari-report-{result.run_id or 'latest'}.json",
                mime="application/json",
                type="primary",
            )
        with html_tab:
            stored_run = RunStore(settings.runs_dir).load(result.run_id)
            st.download_button(
                label="Download Bug Report (HTML)",
                data=render_html(stored_run),
                file_name=f"bugsafari-report-{result.run_id or 'latest'}.html",
                mime="text/html",
            )

        with st.expander("Preview JSON report"):
            st.code(report_json, language="json")


components.html(
    """
    <script>
    (() => {
      try {
        const win = window.parent;
        const doc = win.document;
        if (win.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
        const touch = win.matchMedia('(pointer: coarse)').matches;
        ['bugsafari-pointer-style','bugsafari-cursor-dot','bugsafari-cursor-ring','bugsafari-spotlight']
          .forEach(id => doc.getElementById(id)?.remove());
        const css = doc.createElement('style');
        css.id = 'bugsafari-pointer-style';
        css.textContent = `
          #bugsafari-cursor-dot,#bugsafari-cursor-ring,#bugsafari-spotlight { position:fixed;pointer-events:none;z-index:9999; }
          #bugsafari-cursor-dot { width:6px;height:6px;margin:-3px;border-radius:50%;background:rgb(214,255,114);box-shadow:0 0 10px rgb(214,255,114);transform:translate3d(-100px,-100px,0); }
          #bugsafari-cursor-ring { width:34px;height:34px;margin:-17px;border:1px solid rgb(214 255 114 / 85%);border-radius:50%;transform:translate3d(-100px,-100px,0);transition:width .16s,height .16s,margin .16s; }
          #bugsafari-spotlight { width:480px;height:480px;margin:-240px;border-radius:50%;background:radial-gradient(circle,rgb(214 255 114 / 14%),transparent 68%);transform:translate3d(-700px,-700px,0); }
          .bugsafari-hover-card { transition:transform .16s ease,box-shadow .16s ease;transform-style:preserve-3d; }
          @media(pointer:fine) { body.bugsafari-cursor-on,body.bugsafari-cursor-on * { cursor:none!important; } }
        `;
        doc.head.appendChild(css);
        const dot=doc.createElement('div'),ring=doc.createElement('div'),spot=doc.createElement('div');
        dot.id='bugsafari-cursor-dot';ring.id='bugsafari-cursor-ring';spot.id='bugsafari-spotlight';
        [dot,ring,spot].forEach(el=>{el.setAttribute('aria-hidden','true');doc.body.appendChild(el);});
        const cards=[...doc.querySelectorAll('[data-testid="stVerticalBlockBorderWrapper"]')];
        cards.forEach(card=>{
          card.classList.add('bugsafari-hover-card');let rect;
          card.addEventListener('pointerenter',()=>{rect=card.getBoundingClientRect();});
          card.addEventListener('pointermove',event=>{
            if(touch||!rect)return;
            const px=(event.clientX-rect.left)/rect.width,py=(event.clientY-rect.top)/rect.height;
            card.style.transform=`perspective(900px) rotateX(${(0.5-py)*2}deg) rotateY(${(px-0.5)*2}deg) translateY(-2px)`;
          });
          card.addEventListener('pointerleave',()=>{rect=null;card.style.transform='';});
        });
        if (!touch) {
          doc.body.classList.add('bugsafari-cursor-on');let x=-100,y=-100,rx=x,ry=y,frame=0;
          doc.addEventListener('pointermove',event=>{
            x=event.clientX;y=event.clientY;
            const active=Boolean(event.target.closest('button,a,[data-testid="stVerticalBlockBorderWrapper"]'));
            ring.style.width=active?'46px':'34px';ring.style.height=active?'46px':'34px';ring.style.margin=active?'-23px':'-17px';
            if(!frame)frame=win.requestAnimationFrame(function tick(){
              rx+=(x-rx)*0.2;ry+=(y-ry)*0.2;
              dot.style.transform=`translate3d(${x}px,${y}px,0)`;
              ring.style.transform=`translate3d(${rx}px,${ry}px,0)`;
              spot.style.transform=`translate3d(${x}px,${y}px,0)`;
              frame=Math.abs(x-rx)+Math.abs(y-ry)>0.6?win.requestAnimationFrame(tick):0;
            });
          });
        }
      } catch (_) { /* Optional effect; all controls work without it. */ }
    })();
    </script>
    """,
    height=1,
    scrolling=False,
)
