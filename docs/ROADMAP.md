# Roadmap

Four milestones. Each is independently shippable; stopping after any of them leaves a
coherent, tested product. Phase numbers refer to [PLAN.md](PLAN.md).

```
M1  Data-driven core        P0 ─ P1 ─ P2 ─ P3
M2  Small failures, real reports   P4 ─ P5
M3  Usable surfaces         P6 ─ P7
M4  Extensible + shippable   P8 ─ P9
```

## M1 — Data-driven core

**Theme:** the same run, described as data, executed with bounds, judged by rules that do not
know the fixture.

Ships: flattened repo with git history, `pyproject.toml`, `Settings`, JSON scenarios,
validated loader, external-URL support, timeout-aware executor, `Snapshot` extraction,
five-rule registry, `RunStatus` enum.

Answers the README's milestone 1 ("scenario definitions and configurable action sequences,
plus more independently seeded invariants").

Definition of done
- Seeded bug detected with `$36.00` / `$18.00` using a price-free rule.
- No core module imports `app` or `demo_app`.
- Editing a JSON file changes behavior with no Python edit.
- Unit suite runs in seconds without a browser.

Demo for this milestone: `python -m bugsafari run --scenario cart-total-quantity` (temporary
entry point) or the retained `run_demo_exploration()`.

## M2 — Small failures, real reports

**Theme:** a finding becomes a durable artifact with the shortest reproduction.

Ships: ddmin minimizer with budgets, run store with ids and atomic writes, `run.json`,
`report.md`, screenshot per run, golden-file tests.

Answers the README's milestone 2 ("failure minimization that removes actions while preserving
a confirmed finding").

Definition of done
- Six-step scenario with redundant steps reports a three-step repro.
- Two runs produce two directories and two history rows.
- A report alone is enough to reproduce and understand the failure.

## M3 — Usable surfaces

**Theme:** humans and automation use the same engine.

Ships: CLI (`run`, `scenarios`, `runs`, `doctor`), documented exit codes, bootstrap scripts,
Streamlit v2 with history and downloads, non-blocking runs, friendly environment errors.

Definition of done
- Clone → bootstrap → run → report in under five commands.
- Dashboard reopens a stored run without a browser launch.
- Exit codes usable in CI (`1` = bug found is a *successful* detection).

## M4 — Extensible and shippable

**Theme:** a seam for planning, and quality gates that keep it honest.

Ships: `Planner` protocol, scripted + seeded-random planners, optional LLM planner with
fallback, CI workflow, coverage report, refreshed docs, removal of the compatibility adapter.

Answers the README's milestone 3 ("pluggable planner interface and evaluation of an optional
LLM planner against the deterministic baseline").

Definition of done
- `--planner llm` without a key degrades cleanly and opens no socket.
- Five consecutive scripted runs are byte-identical apart from ids/timestamps.
- CI green from a clean checkout.

## Progress log

Append one line per completed phase: date, phase, commit range, notable deviations.

| Date | Phase | Result | Notes |
|------|-------|--------|-------|
| — | — | not started | docs prepared 2026-10-26; awaiting approval |

## Stretch (post-M4, only if the core is solid)

- Scenario authoring helper that records a manual Playwright session into JSON.
- Finding deduplication across a run history (same signature, repeated occurrences).
- Shrinking of *values* as well as steps (e.g. quantity 99 → 2).
- HTML report with embedded screenshot for sharing.
- Second seeded defect (e.g. rounding) to prove rules generalize.
