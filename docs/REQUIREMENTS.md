# Requirements

Scope: turn the current one-off demo into a usable, deterministic exploration tool without
losing the thing that makes it credible — a real browser run with rule-based detection.
Detection is never delegated to a language model.

## 1. Goals

1. Run the same seeded-bug scenario from data, not code.
2. Point the same engine at any URL, not just the bundled Flask app.
3. Detect a defect without hard-coding the fixture's prices.
4. Produce a durable, human-readable, reproducible report for every run.
5. Shrink a failing sequence to the shortest one that still fails.
6. Make the whole thing runnable from a CLI and inspectable from the dashboard.
7. Leave a clean seam for an optional LLM planner that is never required.

## 2. Non-goals

- Writing fixes or pull requests against the application under test.
- Crawling arbitrary sites at scale, authentication flows, or multi-page journeys.
- Visual regression, performance profiling, or accessibility auditing.
- A hosted service, database, or user accounts.
- Judging correctness with an LLM. Not now, not in the optional path.

## 3. Functional requirements

| ID | Requirement | Acceptance criteria |
|----|-------------|---------------------|
| FR-01 | Scenarios are external data | `scenarios/cart-total-quantity.json` fully describes today's run; editing the file changes the run with no Python edits |
| FR-02 | Scenario validation | Unknown action, unknown rule, or missing required field fails at load with a message naming the scenario id and field |
| FR-03 | Pluggable target | `--url http://host:port` drives an external app with the same executor; `target.kind="local_demo"` starts the bundled server |
| FR-04 | Deterministic step execution | Each step has a timeout and a recorded outcome; total run time is bounded; failures carry step index, action, target, message |
| FR-05 | Rule registry | ≥ 5 named rules, including at least one that detects the seeded bug without catalog prices |
| FR-06 | Finding vs error | A confirmed violation is `bug_detected`; a rule that cannot evaluate, a timeout, or a browser error is `execution_error` with a reason; the two are never conflated |
| FR-07 | Failure minimization | The original and minimized sequences are both reported, with attempt counts; minimization never changes the finding signature |
| FR-08 | Durable run artifacts | Every run writes `run.json`, `report.md`, and a screenshot to `.bugsafari/runs/<run-id>/`, readable by a later process |
| FR-09 | Report content | Report states scenario, status, violated rule, expected vs actual, numbered reproduction steps, environment (Python/browser versions), timestamp |
| FR-10 | CLI | `run`, `scenarios list`, `runs list`, `runs show`, `doctor`; documented exit codes 0/1/2 |
| FR-11 | Dashboard parity | Dashboard can pick a scenario, run it, view the finding, browse past runs, and download artifacts; it calls the same service as the CLI |
| FR-12 | Regression preserved | The seeded quantity bug is still detected with expected `$36.00` and actual `$18.00` |
| FR-13 | Planner seam | `Planner` protocol with a scripted default; optional LLM planner that degrades to scripted and is off unless configured |
| FR-14 | Setup | A documented one-command bootstrap (venv, deps, chromium) plus `python -m bugsafari doctor` reporting what is missing |

## 4. Non-functional requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-01 | No network or API key required | Default install → demo → tests all offline (localhost only) |
| NFR-02 | Determinism | Same scenario + same app ⇒ identical status, finding, and step list across 5 consecutive runs; randomness only via explicit seed |
| NFR-03 | Test speed | Unit suite < 5 s; full suite incl. one browser run < 90 s on a laptop |
| NFR-04 | Portability | Python 3.11+ on Windows and Linux; no POSIX-only APIs |
| NFR-05 | Code quality | `ruff` clean, public functions typed, no dead modules |
| NFR-06 | Safety | No secrets in repo; run artifacts gitignored; no arbitrary code execution from scenario files (data only, never `eval`) |
| NFR-07 | Observability | A failed run explains itself from the report alone — no need to reproduce to learn which step failed |
| NFR-08 | Accessibility of selectors | Interaction exclusively through `data-testid`, never CSS position or text matching for actions |
| NFR-09 | Backward compatibility | `run_demo_exploration()` and the existing tests keep working until M4 |
| NFR-10 | Dependency discipline | No new runtime dependency without an ADR; dev-only additions (`ruff`, `mypy`) are permitted |

## 5. Acceptance scenarios

**AC-1 — Regression.** `python -m pytest` passes from a clean checkout after the documented
setup. `tests/integration/test_seeded_bug.py` reports `$36.00` expected, `$18.00` actual.

**AC-2 — Data-driven.** Delete `bugsafari/engine/explorer.py`'s hard-coded steps (replaced by
the JSON scenario) and the same run still detects the bug.

**AC-3 — Price independence.** Change the Trail Mug price in `shop.html` to `$20.00`; the
`internal_totals_consistent` rule still detects the stale aggregate (`$40.00` line vs
`$20.00` total), proving detection does not depend on baked-in prices.

**AC-4 — External target.** With the demo started manually on port 5000,
`python -m bugsafari run --scenario cart-total-quantity --url http://127.0.0.1:5000`
returns exit code 1 and writes a report.

**AC-5 — Minimization.** Given a six-step scenario whose last three steps are irrelevant to
the failure, the reported minimized sequence is three steps and the signature is unchanged.

**AC-6 — Error honesty.** Point the runner at a closed port: status is `execution_error`,
exit code 2, no screenshot claim, and the report names the connection failure.

**AC-7 — Durability.** `python -m bugsafari runs list` after two runs shows two rows, newest
first; `runs show <id>` prints the stored report without launching a browser.

**AC-8 — Dashboard.** Streamlit starts, a run completes, the finding renders, and a prior run
can be reopened from history after a page reload.

**AC-9 — Offline planner.** With no API key set, planner selection `llm` warns and falls back
to scripted; no network call is attempted and the run still completes.

## 6. Traceability

| Requirement | Phase | Primary test |
|-------------|-------|--------------|
| FR-01, FR-02 | P1 | `tests/unit/test_scenario_loader.py` |
| FR-03, FR-04 | P2 | `tests/integration/test_external_target.py`, `tests/unit/test_executor.py` |
| FR-05, FR-06 | P3 | `tests/unit/test_rules.py` |
| FR-07 | P4 | `tests/unit/test_minimizer.py` (simulated) + `tests/integration/test_minimize_seeded.py` |
| FR-08, FR-09 | P5 | `tests/unit/test_report.py`, `tests/unit/test_store.py` |
| FR-10 | P6 | `tests/cli/test_cli.py` |
| FR-11 | P7 | `tests/integration/test_dashboard_apptest.py` |
| FR-12 | all | `tests/integration/test_seeded_bug.py` (must stay green) |
| FR-13 | P8 | `tests/unit/test_planner.py` |
| FR-14 | P0/P9 | `python -m bugsafari doctor` in CI |
| NFR-02 | all | repeated-run determinism test |
| NFR-03 | P9 | CI timing budget assertion |
