# Decisions (ADR log)

Format: Context → Decision → Consequences. Statuses: Accepted, Proposed (needs owner
confirmation), Superseded.

---

## ADR-001 — Flatten the project directory and initialise git
**Status:** Proposed (D1, D2)
**Context:** The download contains `BugSafari-main/BugSafari-main/`, and the tree is not a git
repository. Every documented command assumes the project root, and there is no way to revert a
failed refactor.
**Decision:** Move the inner contents up one level, then `git init` and commit the untouched
state as the baseline.
**Consequences:** Paths become `python -m demo_app.app`, `streamlit run app/dashboard.py` as
documented. Rollback becomes possible. Moving files before any code change confines the risk to
P0 and makes later diffs readable.

---

## ADR-002 — Scenarios are JSON, not YAML
**Status:** Accepted
**Context:** Scenarios must be editable by non-Python users without adding a parser dependency.
**Decision:** JSON via the standard library, validated by a hand-written loader with precise
error messages.
**Consequences:** No new dependency; comments are impossible, so each scenario gets a `name` and
`description` field. YAML can be added later behind the same loader interface.

---

## ADR-003 — Dataclasses instead of pydantic
**Status:** Accepted
**Context:** `models.py` already uses dataclasses. Adding pydantic would bring a validation
framework for a handful of shapes.
**Decision:** Frozen dataclasses plus explicit `validate()` functions in the loader.
**Consequences:** Zero runtime dependency, full control over messages, slightly more loader code.
Serialization stays `asdict`-based with a `schema_version` on the run document.

---

## ADR-004 — One managed Flask server per local run, bound to port 0
**Status:** Accepted (extends existing behavior)
**Context:** `explorer.py` already does this well; a fixed port collides with a manually started
demo.
**Decision:** Keep `make_server(host, 0, factory)` with a readiness probe and guaranteed shutdown.
Move it into `engine/target.py` so the runner is not demo-aware.
**Consequences:** Runs are isolated and parallel-safe. The demo URL is only known after bind, so
it is returned from the context manager rather than read from settings.

---

## ADR-005 — Rules operate on a `Snapshot`, never a live page
**Status:** Accepted
**Context:** Detection currently mixes DOM access (`controller.read`) with arithmetic, so rules
cannot be tested without a browser.
**Decision:** The browser layer extracts one `Snapshot` (catalog, cart, captured texts, row
count); rules are pure `Snapshot -> Finding | None`.
**Consequences:** The entire detection layer becomes unit-testable in milliseconds, rules can be
evaluated repeatedly during minimization without extra interaction, and a future non-browser
target can feed the same structure.

---

## ADR-006 — Detection stays deterministic; no LLM judges correctness
**Status:** Accepted
**Context:** The project's value is credible, reproducible findings. An LLM verdict is neither.
**Decision:** All pass/fail decisions come from named Python rules. The optional planner may
choose *actions*, never the verdict.
**Consequences:** Findings are explainable and stable. The LLM can only widen exploration. Any
future model-assisted *triage* must remain advisory and clearly labelled.

---

## ADR-007 — Run artifacts live in `.bugsafari/runs/<run-id>/`
**Status:** Proposed (D4)
**Context:** `artifacts/latest.png` is overwritten each run and is CWD-relative, so nothing can be
reopened or compared.
**Decision:** Every run writes its own directory with `run.json`, `report.md`, screenshot and
optional `minimized.json`. `.bugsafari/` is gitignored. `artifacts/latest.png` is still written
for backward compatibility.
**Consequences:** History is trivial to list, the dashboard can reopen runs without a browser, and
disk grows linearly — mitigated by a documented prune step.

---

## ADR-008 — Keep Playwright's synchronous API
**Status:** Accepted
**Context:** The whole codebase is synchronous; the Streamlit dashboard can run a blocking job in
a worker thread.
**Decision:** Stay on `sync_playwright`. No async migration.
**Consequences:** Simpler code and easier debugging. Concurrency, if ever needed, uses threads or
separate processes, not an async rewrite.

---

## ADR-009 — Preserve `run_demo_exploration()` as an adapter
**Status:** Accepted (D7)
**Context:** The README, the seeded-bug test, and possibly the hackathon demo depend on it.
**Decision:** Keep the function as a thin wrapper over the new runner with the same signature and
`RunResult` shape; remove it in M4 after the CLI is documented as the primary path.
**Consequences:** No big-bang migration. Two entry points exist temporarily, which is acceptable
only if the wrapper contains no logic of its own.

---

## ADR-010 — Only dev-only dependencies are added
**Status:** Accepted
**Context:** Runtime deps are four well-known packages; the project should stay trivially
installable.
**Decision:** `requirements.txt` keeps Flask, Playwright, Streamlit, pytest. `ruff` (and optional
`mypy`) go in `requirements-dev.txt`.
**Consequences:** `pip install -r requirements.txt` remains enough to run the demo. Any new
runtime dependency requires a new ADR.

---

## ADR-011 — Keep Streamlit for the UI
**Status:** Proposed (D6)
**Context:** A custom frontend is weeks of work and adds nothing to the detection story.
**Decision:** Improve the existing Streamlit app: scenario picker, run history, artifact
downloads, threaded execution.
**Consequences:** Fast to ship, easy to demo, limited styling. A shareable HTML report (stretch)
covers the "send it to someone" need better than a screenshot.

---

## ADR-012 — `RunStatus` becomes an enum
**Status:** Accepted
**Context:** `status` is a bare string compared in the UI; a typo changes behavior silently.
**Decision:** `enum.StrEnum`-style enum (or `str, Enum`) with `PASSED`, `BUG_DETECTED`,
`EXECUTION_ERROR`. Serialization uses `.value` so `run.json` stays human-readable.
**Consequences:** Exhaustive `match` over statuses; tests assert the enum, not literals on the
UI side.

---

## ADR-013 — Planner is a protocol with a mandatory scripted fallback
**Status:** Accepted (D5)
**Context:** Exploration is the stated next milestone, but nothing may require an API key.
**Decision:** `Planner` protocol; `scripted` is the default and always available;
`seeded_random` for bounded exploration; `llm` is optional and falls back to scripted on any
error, timeout, or missing configuration.
**Consequences:** The demo and CI never touch the network. Evaluation of an LLM planner stays
possible later without restructuring. Validation of planner output is mandatory — a planner may
not emit an unknown action.

---

## ADR-014 — Primary invariant must not know the catalog
**Status:** Accepted
**Context:** Today's check hard-codes `trail-mug: 1800`, so it proves the fixture agrees with
itself rather than that the page is consistent.
**Decision:** Make `internal_totals_consistent` (total == subtotal == checkout total) the primary
assertion; keep the price-based rule as a secondary check.
**Consequences:** Changing any price still detects the stale aggregate (AC-3). Detection survives
catalog edits, which is what makes the tool look like a tester rather than a fixture echo.
