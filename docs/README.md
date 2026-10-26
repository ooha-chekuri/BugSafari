# BugSafari — Supporting Documentation

Documentation set for extending the existing BugSafari vertical slice into a reusable,
deterministic web-exploration engine.

**Status:** planning only. No production code has been modified yet.
**Last updated:** 2026-10-26
**Project root:** the inner `BugSafari-main/` folder (see [D1](PLAN.md#open-decisions)).

## Read in this order

| # | Document | What it answers |
|---|----------|-----------------|
| 1 | [AUDIT.md](AUDIT.md) | What exists today, file by file, and what is wrong with it |
| 2 | [REQUIREMENTS.md](REQUIREMENTS.md) | What the built system must do (FR/NFR + acceptance criteria) |
| 3 | [ARCHITECTURE.md](ARCHITECTURE.md) | How it is structured now vs. the target structure and APIs |
| 4 | [PLAN.md](PLAN.md) | The phased build plan, task lists, and acceptance gates |
| 5 | [ROADMAP.md](ROADMAP.md) | Milestones M1–M4 and what "done" means for each |
| 6 | [TESTING.md](TESTING.md) | Test matrix, fixtures, commands, CI, determinism rules |
| 7 | [RISKS.md](RISKS.md) | Risk register + technical-debt inventory |
| 8 | [DECISIONS.md](DECISIONS.md) | ADR log: why the plan looks like this |

## One-paragraph summary

BugSafari currently proves one thing end to end: Playwright drives a local Flask shop,
changes a line-item quantity, reads the displayed total, and a Python invariant detects
that the total was never recalculated (`$18.00` shown, `$36.00` expected). The browser,
detection, and reporting packages are cleanly separated *by name*, but the engine is
hard-wired to that single demo and scenario. The build plan externalises scenarios into
data, adds a step executor with timeouts and structured errors, turns detection into a
rule registry, adds failure minimization, persists reproducible reports, adds a CLI and a
run-history dashboard, and leaves an optional LLM planner behind an interface. Detection
stays 100% deterministic Python — no model judges correctness.

## Ground rules for the build

1. The seeded bug must remain detectable at every commit (`tests/test_seeded_bug.py`).
2. No network access or API key is required for the default test suite or demo.
3. The core (`bugsafari/`) must never import `app/` or `demo_app/`.
4. Every phase ends with the full suite green and docs updated in the same change.
5. Money is always integer cents internally; formatting happens only at the edge.
