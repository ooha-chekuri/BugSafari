# BugSafari

**Autonomous web exploration and reproducible browser testing**

BugSafari runs bounded browser scenarios, checks application behavior against deterministic rules, verifies findings by replay, and records reproduction steps. This repository is the existing functional-testing prototype. The BugSafari 2.0 work described below is an implementation plan based on the product requirements document; planned capabilities are not claims about the current build.

## What exists today

The current codebase includes a Streamlit dashboard (`app/dashboard.py`), Playwright browser control and snapshots (`bugsafari/browser/`), scenario and action execution (`bugsafari/scenarios/` and `bugsafari/engine/`), deterministic cart rules (`bugsafari/detection/`), run and finding models plus JSON reporting (`bugsafari/reporting/`), a Flask demo shop (`demo_app/`), and tests (`tests/`). There is also a logical concurrent-agent coordinator in `bugsafari/engine/multi_agent.py`; this is not by itself proof of isolated Playwright browser contexts or a complete user-bot swarm.

The dashboard now defaults to a read-only scan of a user-supplied website URL. It captures DOM observations and runs deterministic geometry/image/accessibility checks at responsive widths. The bundled cart scenarios remain an optional demo mode. Browser-backed website verification, goal-directed crawling, and a persona-driven browser-isolated user-bot swarm remain unfinished. See the [gap analysis](docs/PRD_GAP_ANALYSIS.md) for requirement status and environment limitations.

## BugSafari 2.0 implementation guide

Implement incrementally on top of the existing modules. Keep the demo runnable, preserve existing scenario/report compatibility where possible, and make each phase a small reviewable change. The PRD priority labels govern scope: finish P0 foundations before P1; leave P2 and scope-guard items for later. Do not rewrite the application as a greenfield project.

### Phase 1 — Baseline, audit, and traceability

1. Confirm the repository, branch, working-tree changes, and current test baseline before editing. Preserve user changes.
2. Read the complete BugSafari 2.0 PRD and map each requirement to existing code, a gap, and a verification step. Record the map in a maintained implementation checklist or issue tracker.
3. Inspect the dashboard, browser controller and snapshot, explorer/planner/executor, detection rules, models/reporter/store, minimizer/replay, demo defects, and tests.
4. Keep a PRD traceability table with status (`existing`, `partial`, `planned`, `verified`), implementation location, and test/demo evidence. Do not mark a requirement complete because a module exists.

### Phase 2 — Shared finding and state contracts

Extend `bugsafari/reporting/models.py` and browser snapshots with backward-compatible structured data for category, severity, stable rule/bug ID, expected and observed values, selector/location, viewport and measurements, state and ordered path, minimized path, replay status, bot attribution, and review status. Define serialization defaults and migration behavior for existing JSON reports. Use the PRD categories **Functional**, **UI/UX**, **Image**, and **Accessibility**, and text labels for Critical, High, Medium, and Low severity.

Keep rule evaluation deterministic and based on captured state. The planner can suggest actions, but must not decide that a bug exists. Retain the existing cart invariants and their regression scenarios.

### Phase 3 — Observation and P0 checkers

Extend `bugsafari/browser/snapshot.py` to capture the DOM facts checkers need (visible element bounds, computed styles, image natural/rendered sizes and alt data, accessible names/labels, and viewport). Keep extraction in the browser layer and rule decisions in `bugsafari/detection/` so checks can be tested independently.

Implement conservative deterministic P0 checks:

- UI/UX: genuine unintended visible overlap, clipping/off-screen content and horizontal overflow, interactive targets below 24×24 CSS pixels, configurable small text threshold (default 12 px), and responsive measurements at 375, 768, and 1280 px.
- Images: broken resources, likely distortion that accounts for CSS `object-fit` and intentional sizing, viewport/container overflow, and absent or empty alt text on meaningful images.
- Accessibility: text contrast (4.5:1 normal, 3:1 large), unlabeled form controls, and buttons/links without accessible names. Report only this implemented subset; do not claim full WCAG 2.2 conformance.

Exclude hidden elements and avoid treating normal containment or every intersecting box as a defect. Add positive and negative checks for each rule. P1 items such as console/network/HTTP failures, oversized/pixelated images, and broader accessibility checks follow only after P0 is stable.

### Phase 4 — Bounded goal-driven exploration and paths

Extend `bugsafari/engine/` with a validated structured action contract for click, type, select, navigate, and scroll. Accept a target URL and user goal; enforce allowed domains (including redirects), per-run action/time budgets, visited-state tracking, and a strict permitted-action schema. Reject malformed planner output and never execute model-proposed code.

Provide a deterministic or rule-assisted fallback so the demo works without credentials or network access. If an optional LLM planner is configured, validate its JSON output and clearly identify fallback use. Record every action and resulting state; associate each finding with the complete discovery path and readable breadcrumb.

### Phase 5 — Real multi-bot orchestration

Build on or replace the existing logical coordinator only as needed. A bot run must create its own Playwright browser context and isolated storage, stable bot ID, persona/task, independent action/time budget, state/action history, findings, and status. Use a bounded worker pool (default around 5) for configurable 1–100 bots; queue remaining work rather than launching all browsers at once. Enforce per-run action and LLM-call budgets, clean up contexts on errors/cancellation, and limit LLM use to a configured subset.

Merge findings by stable rule, selector, and component where possible; retain all discovering bot/persona attributions and alternate paths, choosing the shortest **verified** path as primary. Summarize completed, failed, and crashed bots, unique states, and findings. Label shared-state scenarios separately; this is user-flow exploration, not load testing. Verify isolation and concurrency limits with tests before attempting a 100-bot run.

### Phase 6 — Verification, minimization, and text-only reports

For a candidate finding, preserve its original ordered path, remove actions in bounded trials, and keep a reduction only after replay confirms the same deterministic rule/signature. Record original/minimized lengths and `reproduced`, `not_reproduced`, or `flaky`; preserve the original path when minimization cannot be verified. Export a candidate Playwright regression test where supported.

Extend the report builder so each text-only finding includes severity/category, rule, expected versus observed behavior, location (selector, page, viewport, measurements), discovery and minimized paths, replay result, and bot attribution. A standalone text-only HTML report is now implemented alongside JSON. Screenshots may be internal debugging artifacts, but must not appear or be embedded in dashboard reports, JSON, HTML, or exported PDF. The dashboard and report exporters omit screenshot content and references. Keep PDF export P1 unless all required P0 work is complete.

### Phase 7 — Dashboard and seeded evaluation

Extend the existing Streamlit dashboard rather than replacing it. Add URL/goal, bot/persona, action/time budget, viewport and checker controls; actual progress/status; summaries and filters; text-only findings with full/minimized paths, replay and bot attribution; and JSON/HTML downloads. Display only results from the current or stored run—never hardcode sample metrics as run results.

Retain existing demo scenarios and add deterministic, stable-selector seeded defects across the four categories. Document each intentional defect. Add reproducible evaluation commands for seeded-bug discovery by category, precision/false positives, replay success, path reduction/completeness, unique states, duplicate reduction, and comparable 1/10/100-bot runs versus a small scripted baseline. Publish only measured results; if 100 bots are not run, state that and document the command to reproduce it.

### Phase 8 — Acceptance and release checks

Run the complete available test suite and relevant browser-backed demo after changes. Add coverage for model serialization, checker positives/negatives, viewport sweeps, action/domain validation, budgets/state tracking, bot isolation/concurrency/cleanup, deduplication/attribution, replay-verified minimization, and text-only JSON/HTML output. Confirm that reports contain no screenshot data. Compare final test results with the recorded baseline and investigate regressions.

Use the PRD acceptance criteria as the release gate: a demo run finds issues in at least three categories; all report entries have severity/category, rule, expected/observed, location, discovery path and no screenshots; reproducible findings have verified minimized paths and replay status; and a 100-bot run uses bounded concurrency and produces one attributed, deduplicated report. Demonstrate at least one bug in each category live and report only actual evaluation metrics.

## Requirement priorities and boundaries

- **P0:** bounded goal-oriented exploration, deterministic functional/UI/image/accessibility checks, common bug/path model, severity-aware text-only reports, verified minimization/replay, isolated multi-bot orchestration and deduplication, dashboard controls, JSON/HTML reports, and reproducible evaluation.
- **P1:** browser console/network/HTTP checks, oversized/pixelated image rules, PDF export, and other follow-on checks identified by the PRD.
- **P2 / deferred:** vision-model second opinion, automatic code repair, state map, shared bot memory, CI integrations, distributed runs, and full WCAG conformance. Never imply these are supported unless implemented and verified.

The PRD's scope guard drops vision second opinion, PDF, state map, shared bot memory, then P1 work first when time is limited. Bug paths, severity highlighting, and real bounded multi-bot runs remain core release requirements.

## Setup

Requirements: Python 3.11+, Git, and Playwright Chromium.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
```

The dashboard opens in **Website URL** mode: enter an `http://` or `https://` address to scan that website. No LLM key is needed. The bundled cart demo remains an explicit optional mode for its deterministic functional scenarios. Optional planner settings and current configuration are documented in `.env.example`; copy it to `.env` only when changing settings.

## Run the current dashboard and tests

```powershell
python -m streamlit run app/dashboard.py
python -m pytest -q
```

In Website URL mode, enter the site and choose **Scan Website**. The current scan inspects the supplied page at mobile, tablet, and desktop widths for deterministic layout, image, and accessibility issues. It does not yet crawl links, complete user goals, or submit forms. Choose **Bundled demo scenario** only when you want to run the bundled cart tests. Existing scenario data is under `scenarios/`; the demo shop is in `demo_app/`.

## Code map

```text
app/dashboard.py              Streamlit UI
bugsafari/browser/             Playwright control and page snapshots
bugsafari/detection/           Deterministic rules and evaluation
bugsafari/engine/              Exploration, execution, planning, replay/minimization,
                               and logical agent coordination
bugsafari/reporting/           Finding/run models, storage, and reports
bugsafari/scenarios/           Scenario models and loading
scenarios/                     Scenario JSON configuration
demo_app/                      Local seeded target application
tests/                         Unit and browser/integration coverage
docs/                          Supporting architecture, requirements, and plans
```

## Configuration

See [`.env.example`](.env.example) for supported settings. Current defaults use the bundled demo, scripted planning, headless browser execution, and local artifact/run directories. An LLM API key is not required for the default workflow.

## Contributors

- Ooha Chekuri
- Hari Kowshik

## License

Add the project's chosen license before distributing it publicly.
