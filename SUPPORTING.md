# SUPPORTING — BugSafari Build Documentation

Entry point for the documentation set prepared on **2026-10-26**. Nothing in the application
has been changed yet; this is the plan, written before code so it can be reviewed and approved.

## Documents

| Document | Contents |
|----------|----------|
| [`docs/README.md`](docs/README.md) | Index, ground rules, one-paragraph summary |
| [`docs/AUDIT.md`](docs/AUDIT.md) | File-by-file audit, 18 numbered findings, what already works |
| [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md) | 14 functional + 10 non-functional requirements, 9 acceptance scenarios |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Current vs target design, file tree, API contracts |
| [`docs/PLAN.md`](docs/PLAN.md) | 10 phases (P0–P9), tasks, acceptance gates, open decisions |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | 4 milestones, definition of done, progress log |
| [`docs/TESTING.md`](docs/TESTING.md) | Test matrix, fixtures, determinism rules, CI |
| [`docs/RISKS.md`](docs/RISKS.md) | 15 risks, debt-to-phase mapping, assumptions |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | 14 ADRs with context and consequences |

## The plan in one screen

| Milestone | Phases | Outcome |
|-----------|--------|---------|
| **M1** Data-driven core | P0–P3 | Repo flattened + git, settings, JSON scenarios, pluggable target, bounded executor, `Snapshot`, 5-rule registry, price-independent detection |
| **M2** Small failures, real reports | P4–P5 | ddmin minimization, per-run artifact directories, `run.json`, `report.md` |
| **M3** Usable surfaces | P6–P7 | CLI with exit codes + `doctor`, bootstrap scripts, dashboard with history and downloads |
| **M4** Extensible + shippable | P8–P9 | Planner protocol with optional LLM fallback, CI, coverage, docs refresh |

Current state: one deterministic Playwright scenario, a Flask demo with a deliberately stale
cart total, a Python invariant that catches it, and a single-button Streamlit dashboard.
The build keeps that detection story intact and makes it reusable.

## What I need from you

1. Approve the plan, or name the phases to drop/reorder.
2. Answer the decisions in [`docs/PLAN.md#open-decisions`](docs/PLAN.md#open-decisions) —
   defaults are flatten the folder, `git init`, JSON scenarios, `.bugsafari/runs/`, LLM later,
   keep Streamlit, keep the compatibility adapter.
3. Confirm the definition of done for the first milestone (M1) if you want a smaller first
   delivery.

After approval I start at **P0** and report back after each phase with: files changed, test
results, and the seeded-bug regression output (`$36.00` expected vs `$18.00` actual).
