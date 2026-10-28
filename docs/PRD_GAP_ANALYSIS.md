# BugSafari 2.0 PRD gap analysis

Audit basis: current `master` checkout and source inspection on 2026-10-28. The working tree already contained a user-requested `README.md` change; it was preserved. `master` is three commits ahead and one behind `origin/main`. No branch or history changes were made.

The repository contains a functional scenario runner, sync Playwright controller, cart snapshots/rules, a minimizer, run storage/reporting, Streamlit UI, and logical agent coordination. The existing `MultiAgentCoordinator` caps worker threads and each browser worker creates a fresh context, but the browser worker is a fixed cart probe and its findings are not merged with bot attribution. Those pieces do not satisfy the PRD's goal-driven browser-bot swarm.

Baseline test execution is currently **blocked by the local Python installation**: `python` is not on PATH, and `.venv` points to the missing `C:\Users\oohac\AppData\Local\Programs\Python\Python312\python.exe`. Therefore no baseline pass count is available. Restore a Python 3.11+ interpreter and recreate the virtual environment before using `python -m pytest -q` as the baseline.

## Requirement-to-code map

Status means `partial` where a related prototype exists but the acceptance requirement is not satisfied. `planned` means no implementation was found during this audit.

| PRD IDs | Status | Existing code / gap | Proposed implementation and evidence |
| --- | --- | --- | --- |
| F1, F3 | Partial | `scenarios/website_scan.py` accepts an HTTP(S) URL and creates a read-only single-navigation scan; `engine/executor.py` bounds scenario execution. Goal-directed click/type/select/navigation/scroll exploration and allowed-domain/redirect enforcement are still absent. | Add bounded website exploration, strict action validation, domain/redirect checks, and user-settable action/time budgets. |
| F2 | Partial | `engine/planner.py` has scripted and seeded ordering; no goal-directed LLM structured planner/fallback. | Goal-aware planner protocol, validated JSON output and deterministic fallback; malformed-output/offline tests. |
| F4 | Planned | No page-state deduplication or exploration-efficiency tracking found. | Stable state fingerprint and visited-state budget; repeat-state tests. |
| F5 | Partial | Cart invariants exist in `detection/rules.py`; negative quantity and generic removed-item rules are not established as standalone checks. | Preserve cart rules and add missing deterministic invariants with scenario regressions. |
| F6 | Partial (P1) | Browser worker records console/page errors; no unified failed-request and HTTP status checker in scenario runner. | Add after P0 checker foundation. |
| U1–U4, U6 | Partial (new, browser verification pending) | `browser/snapshot.py` captures visible control/text/image bounds, styles and names; `detection/dom_checks.py` checks overlap, clipping/overflow, small targets/fonts; `engine/runner.py` sweeps 375/768/1280 px. No live browser result verified in this environment. | Complete browser-backed regression tests and validate overlap false-positive rate; refine observer and use actual runs before marking verified. |
| U5 | Planned (P1) | No sibling alignment rule found. | Defer until P0 geometry rules are stable. |
| I1–I3, I6 | Partial (new, browser verification pending) | Observer records natural/rendered dimensions, load state, alt, decoration and `object-fit`; pure rules check broken, distorted, overflowing, and missing meaningful alt images. | Verify broken and valid fixture images across responsive widths, including legitimate fit behavior. |
| I4–I5 | Planned (P1) | No oversized/pixelated image rules found. | Defer until P0 image checks are stable. |
| A1–A3 | Partial (new, browser verification pending) | Observer captures computed foreground/background colors, font size/weight and approximate accessible names/labels; pure rules check contrast, form labels, and button/link names. | Verify browser extraction against real labels/ARIA and test mixed opacity/background cases; this is not a full WCAG audit. |
| A4–A7 | Planned (P1) | No structure, keyboard/focus, or score checks found. | Defer; avoid claiming full WCAG conformance. |
| H1–H4, H7 | Partial | `Finding` now supports category, normalized severity, title, selector, page, viewport, observed measurements and stable ID; Markdown/HTML/JSON output is text-only. Dashboard no longer displays or exports screenshots. Internal screenshot artifacts remain for debugging. | Extend every functional finding with location/ID, add replay/bot facts, and test the complete export contract. |
| H5 | Planned | No severity/category/bot summary strip found. | Aggregate actual run results and display computed counts. |
| H6 | Planned (P1) | No finding filtering/sorting found. | Add after report model/aggregation. |
| B1–B3, B7–B8 | Partial | `engine/multi_agent.py` uses `ThreadPoolExecutor`; `browser_agent_worker.py` creates isolated contexts. Count defaults/ranges, personas, per-bot/run budgets, queued browser-user tasks, and planner subsets are missing. Existing worker is a fixed probe. | Persona-backed tasks, bounded 1–100 roster, per-bot contexts/budgets and controlled planner allocation; isolation/concurrency/failure tests. |
| B4, B9 | Planned (P1) | No shared exploration state or unique-state/crash summary. | Add shared-memory coordination and per-bot metrics after core swarm. |
| B5–B6 | Partial | Coordinator can deduplicate generic `FindingReport`s but does not merge bot/persona attribution or choose shortest verified path. | Stable finding signature, contributing bot list, alternate paths, shortest verified primary path; aggregation tests. |
| G1–G6 | Partial/planned | Functional scenario workflow and logical agent pool exist; unified autonomous multimodal checkers, exports and verified multi-bot report do not. | Delivered only when mapped P0 requirements pass acceptance tests. |
| Replay/minimization | Partial | `engine/minimizer.py` and dashboard replay exist for current scenario findings. Replay status vocabulary and minimized candidate verification are narrower than PRD. | Preserve originals; persist reproduced/not_reproduced/flaky and only accept same-signature verified reductions. |
| Dashboard controls/export | Partial | Existing `app/dashboard.py` runs/replays scenarios, renders finding labels and exports JSON/standalone text-only HTML without screenshot content. PRD run controls, computed bot/category/severity summary, and filters remain absent. | Extend the existing UI after browser-user orchestration and aggregation exist. |
| Seeded evaluation | Partial | Demo app and cart scenarios exist; seeded defects for all four categories and evaluation scripts/metrics not found. | Add deterministic fixtures and measured discovery/replay/precision/path/bot experiments; never fabricate results. |

## Incremental implementation order

1. Restore the Python runtime and record a reproducible baseline before code-level changes.
2. Extend shared findings and DOM snapshots with backward-compatible optional fields.
3. Add pure deterministic UI, image, and accessibility checks and isolated unit tests.
4. Add bounded state-aware exploration, action validation, domain restrictions, and paths.
5. Turn the existing logical coordinator into a real persona-driven isolated browser-bot runner with attribution and budgets.
6. Add verified finding aggregation, text-only JSON/HTML/Markdown reports, then dashboard controls.
7. Seed and measure the demo, run full tests, and report exact completed/partial requirements and limitations.

## Work completed in this increment

- Added backward-compatible DOM observation fields and finding metadata.
- Added deterministic P0 geometry, image, and accessibility checks, configurable small-font threshold, and responsive width sweep.
- Connected the checks to scenario evaluation and added standalone text-only HTML reporting.
- Removed screenshot display from the dashboard and screenshot references from serialized reports; screenshot files remain internal artifacts.
- Added checker, serialization, report, and configuration unit coverage. These tests pass in the available environment, but full browser verification remains blocked because the project venv's Python 3.12 executable is missing and available Python 3.13 lacks a compatible Playwright `greenlet` binary.
- Made the dashboard default to a user-supplied website URL. Website scan mode opens only that page, avoids demo-specific selectors/cart extraction, and runs read-only DOM checks; the bundled demo scenarios are an explicit alternate mode.
- Added URL validation and unit coverage for HTTP(S) website scan setup. The supported isolated test set now has 80 passing tests; full-suite collection and external-site browser checks remain blocked by the local Playwright/Python environment.

Do not label the full P0 scope complete until later phases are implemented and demonstrated.
