# Codebase Audit — Current State

Snapshot of the repository as delivered: 12 Python modules (~300 LOC), one HTML template,
two test files, no packaging metadata, no CI, no git history.

## 1. File inventory

| Path | LOC | Role | Health |
|------|----:|------|--------|
| `README.md` | 69 | Pitch, setup, run instructions, next milestones | Good; describes intent accurately |
| `requirements.txt` | 4 | Flask, Playwright, Streamlit, pytest (range pins only) | OK; no dev/test split, no lockfile |
| `.gitignore` | 9 | Ignores venv, caches, `artifacts/*` | Good |
| `.env.example` | 1 | States that no env vars are needed | Stale after config layer lands |
| `app/__init__.py` | 1 | Package marker | OK |
| `app/config.py` | 7 | `DEMO_HOST`, `DEMO_PORT` (env `BUGSAFARI_PORT`), `SCREENSHOT_PATH` | Too thin; imported by 4 modules |
| `app/dashboard.py` | 60 | Streamlit UI: one button, one run, action log, finding, screenshot | Works; no history, no choices |
| `demo_app/__init__.py` | 1 | Package marker | OK |
| `demo_app/app.py` | 18 | Flask app factory, single `/` route | Clean, but imports `app.config` |
| `demo_app/templates/shop.html` | 68 | Vanilla-JS cart with the deliberate defect | Correct defect isolation |
| `bugsafari/__init__.py` | 1 | Package marker | OK |
| `bugsafari/browser/controller.py` | 41 | 6 Playwright helpers, records `ActionRecord`s | Good idea; no timeouts |
| `bugsafari/engine/explorer.py` | 66 | Managed Flask server + hard-coded scenario | Main source of coupling |
| `bugsafari/detection/invariants.py` | 27 | `parse_money`, `format_money`, `check_cart_total` | Correct logic, brittle inputs |
| `bugsafari/reporting/models.py` | 39 | `ActionRecord`, `Finding`, `RunResult` | Adequate; stringly-typed status |
| `bugsafari/reporting/reporter.py` | 10 | Formats repro steps as numbered lines | Minimal |
| `tests/test_invariants.py` | 16 | Pure unit tests for money + rule | Good, fast |
| `tests/test_seeded_bug.py` | 11 | Browser regression: expects `$36.00` vs `$18.00` | Good intent, over-constrained |

## 2. What already works well

- **Honest scope.** The README states what is deterministic and what is future work.
  There is no LLM in the detection path, and that is the right call.
- **Money as integer cents** (`invariants.py:6`) instead of floats.
- **Test IDs everywhere.** Every interactive element carries `data-testid`
  (`shop.html:25-33,46-56`), so selectors are stable and accessibility-friendly.
- **Ephemeral server on port 0** with a readiness probe and a `finally` shutdown
  (`explorer.py:17-39`). The browser test can run next to a manually started demo.
- **Finding vs. error separation.** A detected defect is a *successful run*; a browser
  failure is a different status (`models.py:30`, `explorer.py:59-65`).
- **Reproduction steps are data**, not formatted prose, so any renderer can use them.
- **The seeded defect is genuinely isolated.** Line totals update; only the aggregate
  totals go stale (`shop.html:52` calls `render(false)`, the guard at `:58` skips the sum).

## 3. Findings

Severity: **H**igh = blocks the next milestone, **M**edium = causes real friction or false
results, **L**ow = polish.

| ID | Sev | Finding | Evidence |
|----|-----|---------|----------|
| A-01 | H | The scenario is hard-coded inside the engine; there is no way to add or select a run without editing Python. | `explorer.py:42-59` |
| A-02 | H | The reusable engine imports the demo fixture and the UI config, so the framework cannot target any other application. | `explorer.py:10,14`, `demo_app/app.py:4` |
| A-03 | H | No packaging metadata or CI; correctness depends on being in the right CWD with the right global interpreter. | no `pyproject.toml`, no `.github/` |
| A-04 | H | Project is nested (`BugSafari-main/BugSafari-main/`) and is not a git repository, so there is no rollback or diff safety net. | directory listing |
| A-05 | M | No action timeouts or step budgets. A single hung selector stalls the run for Playwright's default 30 s per call, and nothing bounds the total. | `controller.py:15-35` |
| A-06 | M | `check_cart_total` raises `KeyError` for an unknown item and `parse_money` raises `ValueError` on non-money text (`"$"`, `""`, `".50"`). Both are caught by the outer handler and reported as *execution errors*, which can mask a real UI defect. | `invariants.py:6-10,21` |
| A-07 | M | Expected prices are hard-coded in the engine (`{"trail-mug": 1800}`) rather than read from the page, so the invariant re-states the fixture instead of observing it. | `explorer.py:58` |
| A-08 | M | A run produces no durable artifact beyond one overwritten screenshot; `artifacts/latest.png` is relative to CWD, so launching from another directory writes elsewhere. | `config.py:7`, `explorer.py:56` |
| A-09 | M | Status is a bare string (`"bug_detected"`, `"passed"`, `"execution_error"`) compared with `==` in the UI; a typo silently changes behavior instead of failing. | `models.py:30`, `dashboard.py:30-35` |
| A-10 | M | The browser regression asserts the exact action-name list `["open","click","fill"]`, so any added instrumentation or step breaks a test that is really about the defect. | `test_seeded_bug.py:10` |
| A-11 | M | The dashboard cannot choose a scenario, target, headless mode, or compare runs; it exposes exactly one button. | `dashboard.py:24-26` |
| A-12 | M | Findings cannot be exported or re-read. `Finding.to_dict()` exists but nothing consumes it. | `models.py:24-25` |
| A-13 | L | `change_quantity` rewrites the previous log entry's result instead of appending a commit action, which couples `fill` and `Tab` and makes the log lie about what happened. | `controller.py:29-32` |
| A-14 | L | `use_container_width=True` is deprecated in recent Streamlit; requirements allow `<2.0`, so warnings will appear. | `dashboard.py:40` |
| A-15 | L | No logging or diagnostics. When a run fails, the only signal is a string in the UI. | `explorer.py:62-65` |
| A-16 | L | No friendly handling when Chromium is not installed; the user sees a raw Playwright exception. | `explorer.py:47-48`, `dashboard.py:35` |
| A-17 | L | Config is duplicated in intent across layers (`app/config.py` read by `app`, `demo_app`, `bugsafari`), with no single settings object. | `config.py:5-7` |
| A-18 | L | Cart totals are not in an `aria-live` region, so a screen-reader user does not hear the stale-total update; `#cart-items` alone is live. | `shop.html:30-33` |

## 4. The seeded defect, precisely

`shop.html` keeps a module-level `shownTotal`. Adding a product recomputes it. Changing a
quantity calls `render(false)` (`:52`), and the guard at `:58` therefore skips the
recomputation, while the per-line total at `:53` is recomputed unconditionally.

| Action | Line total | Subtotal | Total | Checkout |
|--------|-----------:|---------:|------:|---------:|
| Add Trail Mug | $18.00 | $18.00 | $18.00 | $18.00 |
| Set qty → 2 | **$36.00** | $18.00 (stale) | $18.00 (stale) | $18.00 (stale) |
| Remove item | — | $0.00 | $0.00 | $0.00 |

This is a genuine internal-consistency violation, detectable without knowing the catalog:
the line total and the aggregate disagree. The target rebuild should exploit that by
adding a **meta-invariant** ("aggregate equals sum of visible line totals") so detection no
longer depends on hard-coded prices (fixes A-07).

## 5. Test and runtime reality

- `tests/test_invariants.py` runs anywhere, takes milliseconds.
- `tests/test_seeded_bug.py` requires `playwright install chromium`; it boots a real server
  and browser, so it takes seconds and is the only flaky candidate.
- Verified environment on this machine: Python 3.11.9 present; Flask, Playwright,
  Streamlit, and pytest are **not installed**, so no test has been run yet. Phase 0 installs
  them into a virtual environment before any code changes.
- There is no `conftest.py`, no shared fixtures, and no marker separating browser tests from
  unit tests.

## 6. Deliberate non-problems

These look odd but are correct and should be preserved:

- The bug is intentional and must stay reproducible — never "fix" `shop.html`.
- Detection is rule-based by design; the project's credibility rests on determinism.
- The dashboard launching a real browser (rather than canned JSON) is the point.
- `artifacts/*` being gitignored is correct; durable runs belong in an ignored runtime dir.
