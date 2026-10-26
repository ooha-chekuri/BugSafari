# Build Plan

Ten phases, four shippable milestones. Each phase is a small number of commits and ends
with the full suite green, the seeded bug still detected, and these docs updated in the
same change. Phases are ordered so that no phase depends on a later one.

Effort key: **S** ≈ 1 session, **M** ≈ 2–3 sessions, **L** ≈ 4+ sessions.

## Open decisions

These need your call before Phase 0 starts. Defaults are what I will use if you just say
"approved".

| ID | Decision | Options | Default |
|----|----------|---------|---------|
| D1 | Nested folder `BugSafari-main/BugSafari-main/` | (a) flatten one level, (b) leave as-is | **(a) flatten** — every path and command in the docs assumes the project root |
| D2 | Project is not a git repo | (a) `git init` + baseline commit, (b) no version control | **(a) git init** — required to make "revert a phase" possible |
| D3 | Scenario format | (a) JSON (stdlib), (b) YAML (+PyYAML) | **(a) JSON** |
| D4 | Run artifacts location | (a) `.bugsafari/runs/`, (b) `artifacts/runs/` | **(a)** — keeps demo screenshots and run history separate |
| D5 | LLM planner | (a) interface + scripted now, LLM later, (b) build LLM planner in this pass | **(a)** — nothing in the demo may depend on a key |
| D6 | Dashboard tech | (a) keep Streamlit, (b) rewrite frontend | **(a)** — rewrite is out of scope |
| D7 | Backward-compat adapter | (a) keep `run_demo_exploration()` until M4, (b) delete immediately | **(a)** |

---

## P0 — Baseline, packaging, and safety net (S)

**Why:** nothing can be verified today; there is no venv, no test config, no rollback.

Tasks
1. Flatten the nested directory (D1) and `git init` with a single baseline commit (D2).
2. Create `.venv` with Python 3.11, install `requirements.txt`, run
   `python -m playwright install chromium`.
3. Run `pytest` and record the true baseline result (expected: 2 passed).
4. Add `pyproject.toml`: project metadata, `[tool.pytest.ini_options]` with
   `testpaths = ["tests"]` and markers `unit` / `integration` / `cli`, `[tool.ruff]`
   (line length 100, target py311).
5. Add `requirements-dev.txt` (`ruff`, `mypy` optional) and split test/lint commands into
   `docs/TESTING.md`.
6. Extend `.gitignore` with `.bugsafari/`, `.mypy_cache/`, `.ruff_cache/`.
7. Update `.env.example` with the `BUGSAFARI_*` variables introduced in P1 (documented but
   optional).
8. Add `tests/conftest.py` with fixtures: `settings(tmp_path)`, `demo_server`,
   `browser_page`, `run_dir`.

Acceptance
- `pytest` green with an accurate count in the README.
- `ruff check .` clean on the untouched code (fix trivial issues only).
- A failed experiment can be reverted with `git checkout -- .` on the baseline.

## P1 — Settings and scenario data (M)

**Why:** the scenario and the target are the two hard-coded things (A-01, A-02, A-17).

Tasks
1. `bugsafari/config.py`: frozen `Settings` dataclass, `load_settings()`, env overrides,
   `.env` not required.
2. `bugsafari/scenarios/model.py`: `Step`, `InvariantSpec`, `TargetSpec`, `Scenario`
   (frozen dataclasses, no pydantic).
3. `bugsafari/scenarios/loader.py`: locate + parse + validate JSON; errors name scenario id
   and field; reject unknown action/rule at load time.
4. `scenarios/cart-total-quantity.json`: the existing three steps, capture list, invariants.
5. `scenarios/internal-consistency.json`: price-free variant for AC-3.
6. Remove `app/config.py` reads from `demo_app` and `bugsafari`; `app/config.py` becomes a
   thin re-export for compatibility.
7. Keep `explorer.run_demo_exploration()` working by loading the JSON scenario internally.

Acceptance
- Editing the JSON changes the executed steps (proved by a test that swaps the file for a
  temp scenario).
- `pytest` green; seeded bug still `$36.00` / `$18.00`.
- No `bugsafari` module imports `demo_app` or `app` (enforced by a new import-guard test).

## P2 — Target resolution and step executor (M)

**Why:** FR-03/FR-04; today one hidden `open` call is the only step type and nothing is
bounded in time (A-05).

Tasks
1. `bugsafari/engine/target.py`: `TargetSpec` resolution, `managed_local_server()` context
   manager returning a base URL, external URL passthrough. No demo imports.
2. `bugsafari/browser/controller.py`: add timeouts, `press`, `select`, `wait_visible`,
   structured step results. Keep `ActionRecord` shape stable.
3. `bugsafari/engine/executor.py`: action registry, `StepError(index, action, target, msg)`,
   recording of failed steps (A-13 fixed: `change_quantity` logs its own commit).
4. `bugsafari/engine/runner.py`: orchestrates settings → target → browser → executor →
   snapshot → rules → result; the only place that composes layers.
5. Move `BrowserController` creation and browser lifecycle into the runner.

Acceptance
- `tests/unit/test_executor.py` covers every action against a stub page, including timeout
  and unknown-action paths.
- Unknown action in a scenario fails at load, not mid-run.
- External-URL run works against a manually started demo (AC-4 manual check).

## P3 — Snapshot capture and rule registry (L)

**Why:** FR-05/FR-06, A-06, A-07. This is the phase that makes detection real rather than
fixture-aware.

Tasks
1. `bugsafari/browser/snapshot.py`: read catalog from `[data-product][data-price]`, cart
   quantities from quantity inputs, captured texts by test id, row count.
2. `bugsafari/detection/invariants.py`: keep `parse_money`/`format_money`, make money parsing
   total (`None` on unparseable) and add property-style unit tests for edge inputs
   (`""`, `"$"`, `"$1,234.50"`, `"18.5"`, `".50"`).
3. `bugsafari/detection/rules.py`: registry + five rules from the architecture doc, each
   `Snapshot -> Finding | None`, each registering a stable rule id.
4. `bugsafari/detection/engine.py`: evaluate specs in order, collect findings (first finding
   is the primary), convert `RuleError` → `execution_error` with rule id.
5. `bugsafari/reporting/models.py`: add `RunStatus` enum (A-09), `Finding.rule_id`,
   `Finding.signature()`, keep `to_dict()`.
6. Remove hard-coded prices from the engine; delete the `{"trail-mug": 1800}` literal.

Acceptance
- `tests/unit/test_rules.py`: table-driven, no browser; one case per rule, plus malformed
  input and unknown-item cases.
- Seed test still detects the bug using `internal_totals_consistent`.
- Changing the mug price to `$20.00` still yields a confirmed finding (AC-3).

## P4 — Failure minimization (M)

**Why:** FR-07, the second README milestone, and the feature that makes reports useful.

Tasks
1. `bugsafari/engine/minimizer.py`: ddmin over `Step` subsets; signature = `(rule_id,
   expected, actual)`; bounded by attempts and wall clock; deterministic order.
2. Replay uses the runner in a fresh browser context per candidate; failures during replay
   count as "not reproducible", never as success.
3. Result object: `original`, `minimized`, `attempts`, `duration_s`, `reduction`.
4. Wire into runner behind `settings.minimize`; write `minimized.json` in P5.
5. Unit tests use an injected `reproduce(steps) -> Finding | None` callable, so no browser is
   needed; one integration test proves it on the seeded scenario.

Acceptance
- Synthetic six-step scenario with three irrelevant steps minimizes to three (AC-5).
- `attempts <= max_minimize_attempts`; runtime bounded.
- Minimized signature always equals original signature, asserted on every candidate.

## P5 — Run store and reports (M)

**Why:** FR-08/FR-09, A-08, A-12. A finding that cannot be re-read is not a report.

Tasks
1. `bugsafari/reporting/store.py`: run id generation, atomic directory write, `save_run()`,
   `load_run()`, `list_runs()` (newest first), schema version.
2. `bugsafari/reporting/reporter.py`: `render_markdown(run) -> str` with summary, rule,
   expected vs actual, numbered repro, minimized repro, environment, artifacts list;
   `render_json(run) -> dict`; both idempotent for golden tests.
3. Copy the screenshot into the run dir; continue writing `artifacts/latest.png` for the
   legacy path.
4. `run.json` round-trips (`load(save(run)) == run`), including findings and steps.
5. Keep `reproduction_steps()` as a thin wrapper so existing callers keep working.

Acceptance
- Golden-file tests for `report.md` (fixed run fixture) and `run.json`.
- Interrupted write leaves no partial run dir (simulated by raising mid-save).
- `runs list` ordering test.

## P6 — CLI (M)

**Why:** FR-10. CLI is the automation surface and the fastest way to verify anything.

Tasks
1. `bugsafari/cli.py` + `__main__.py` with argparse subcommands from the architecture doc.
2. Rich-free plain output by default; `--json` prints the `run.json` document only.
3. Exit codes 0/1/2 (documented in README and `--help`).
4. `doctor` checks: Python version, imports, Playwright + Chromium presence, port
   availability, scenario directory readable.
5. `scripts/bootstrap.ps1` and `scripts/bootstrap.sh` doing venv + install + chromium.

Acceptance
- `tests/cli/test_cli.py` uses `subprocess` for: `--help`, `scenarios list`, `doctor`,
  and a `run` against a closed port asserting exit 2 (no browser needed for that path).
- One integration CLI test asserts exit 1 and that a run directory was created.

## P7 — Dashboard v2 (M)

**Why:** FR-11, A-11, A-14, A-16. The UI should show what the CLI can do.

Tasks
1. Scenario picker, optional target URL, headless and minimize toggles.
2. Run in a worker thread with a progress indicator; no frozen page during a browser run.
3. Finding card, minimized repro, action table, screenshot.
4. Run history from `store.list_runs()`; selecting a run loads its `run.json` without
   re-running.
5. Download buttons for `report.md`, `run.json`, screenshot.
6. Friendly Chromium-missing message with the exact fix command.
7. Replace deprecated `use_container_width` usage.

Acceptance
- `streamlit.testing.v1.AppTest` smoke test: app renders, run button exists, history empty
  state renders.
- Manual checklist: one live run, reload, reopen from history, download a report.

## P8 — Planner seam and optional LLM (M)

**Why:** FR-13, the third README milestone. Must not put a key in the demo path.

Tasks
1. `bugsafari/planner/base.py`: `Planner` protocol + `load_planner(name, settings)`.
2. `scripted.py` (default, exact scenario steps) and `seeded_random.py` (bounded, reproducible).
3. `llm.py`: provider-agnostic HTTP call behind an env-configured endpoint; compact page
   summary in, JSON steps out; strict validation; timeout; **fallback to scripted** on any
   failure; `available()` returns False with no key.
4. CLI flag `--planner` and dashboard selector; `doctor` reports planner availability.
5. Tests only exercise scripted/seed and the *fallback* path of the LLM planner (mocked
   transport); the real network path is never tested in CI.

Acceptance
- Same scenario, `--planner scripted`, five runs → identical output (NFR-02).
- `--planner llm` with no key → warning + scripted result, no socket opened (asserted by a
  blocked-socket fixture).
- Planner cannot emit an unknown action past validation.

## P9 — Quality gates, docs, and cleanup (M)

**Why:** make the result maintainable and honest.

Tasks
1. Split tests into `tests/unit`, `tests/integration`, `tests/cli`; register markers; make
   `pytest -m "not integration"` the fast default in docs.
2. Coverage target ≥ 85% on `bugsafari/` (report, not a hard gate initially).
3. `.github/workflows/ci.yml`: lint + unit on push; integration job installs Chromium and
   uploads the run artifact.
4. Update `README.md` (setup, CLI, dashboard, architecture links, exit codes, limitations).
5. Refresh `docs/*` to match the built system; close findings in `AUDIT.md` with a status
   column or a "resolved in" note.
6. Optional: remove the `run_demo_exploration()` adapter once tests use the runner directly.
7. Final review pass for dead code, unused imports, and stale comments.

Acceptance
- CI green on a clean checkout.
- `docs/` and code agree; every FR in `REQUIREMENTS.md` has a passing test.
- README gets a user from clone to a report in under five commands.

---

## Verification ritual (every phase)

1. `pytest -m "not integration"` — fast suite.
2. `pytest` — full suite incl. browser.
3. `ruff check .`
4. `python -m bugsafari run --scenario cart-total-quantity` — must exit 1 with `$36.00` / `$18.00`.
5. `git diff --stat` reviewed against the phase's file list; nothing unrelated touched.
6. Docs updated; a changelog line added to `ROADMAP.md` progress log.

## Explicitly out of scope for this build

- Multi-page crawling, sessions/auth, file uploads, iframes, shadow DOM.
- Parallel scenario execution.
- Database, user accounts, hosted deployment.
- Automatic patch generation or PR creation.
- Replacing Streamlit with a custom frontend.
- Training or fine-tuning any model.

## Suggested first slice if time is short

If only M1 can be built, the project still improves materially: data-driven scenarios,
pluggable targets, bounded steps, a five-rule registry, and price-independent detection.
Minimization and reports (M2) are the highest-value follow-up.
