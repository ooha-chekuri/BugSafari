# Risks and Technical Debt

## 1. Risk register

| ID | Risk | Likelihood | Impact | Mitigation | Phase |
|----|------|-----------|--------|------------|-------|
| R-01 | Flattening the nested folder breaks relative paths (`artifacts/`, template lookup, CWD assumptions) | High | Medium | Flatten first, before any code change; run the baseline suite immediately after; fix `artifacts`/`runs` paths to be settings-derived, never CWD-derived | P0 |
| R-02 | No version control means a bad refactor is unrecoverable | High | High | `git init` + baseline commit before Phase 1; commit per task, not per phase | P0 |
| R-03 | Scope is 10 phases; running out of time mid-refactor leaves the repo half-migrated | Medium | High | Milestones are shippable on their own; compatibility adapter keeps the old entry point alive; never leave two competing code paths at the end of a phase | all |
| R-04 | Playwright/Chromium missing on a fresh machine or CI | High | Medium | `doctor` command, bootstrap script, explicit error message, CI installs with deps | P0/P6 |
| R-05 | Browser tests are slow or flaky in CI | Medium | Medium | Single browser instance per session, one integration run per behavior, no retries-as-policy, quarantine rule | P9 |
| R-06 | Detection becomes fixture-aware again (someone re-adds hard-coded prices) | Medium | High | Price-free `internal_totals_consistent` rule is the primary assertion; import/rule tests; AC-3 price-change test | P3 |
| R-07 | A rule that cannot evaluate is misreported as a bug (false positive) | Medium | High | `RuleError` → `execution_error`, never `bug_detected`; explicit per-rule tests for malformed input | P3 |
| R-08 | Minimization replay changes the signature (false minimization) | Medium | High | Signature equality asserted on every candidate; fresh context per replay; budget cap | P4 |
| R-09 | Streamlit reruns block during a browser run, looking like a hang | High | Low | Worker thread + progress placeholder; keep runs short; document expected duration | P7 |
| R-10 | LLM planner leaks into the default path or needs a key to demo | Low | High | Fallback to scripted; `available()` gate; blocked-socket test; no key in `.env.example` | P8 |
| R-11 | Artifacts accumulate unbounded on disk | Medium | Low | Ignored dir, `runs list` shows size, prune command or documented manual cleanup; keep one screenshot per run | P5 |
| R-12 | Hidden coupling: core imports demo again during refactor | Medium | Medium | `test_import_guard.py` in the unit suite, run in CI | P1 |
| R-13 | Goldens churn on every report tweak, hiding real diffs | Medium | Low | Normalize ids/timestamps; one golden per renderer; update goldens only in the same commit as an intentional format change | P5 |
| R-14 | Over-engineering: abstractions nobody uses | Medium | Medium | Every abstraction must be exercised by a test and one caller; no speculative plugin system beyond `Planner` | all |
| R-15 | Windows/Linux divergence (paths, process cleanup, emoji in console) | Medium | Medium | `pathlib` only, no shell=True, ASCII in CLI output, CI on Linux + local Windows | all |

## 2. Technical debt inventory

Maps the audit findings to the phase that resolves them.

| Finding | Debt | Resolved in | Verification |
|---------|------|-------------|--------------|
| A-01 | Hard-coded scenario | P1 | JSON-driven test |
| A-02 | Core imports demo/app | P2 (target) + P1 | import-guard test |
| A-03 | No packaging/CI | P0, P9 | `pytest` from clean checkout, CI |
| A-04 | Nested dir, no git | P0 | baseline commit exists |
| A-05 | No timeouts | P2 | executor timeout test |
| A-06 | Rules raise on bad input | P3 | malformed-input tests |
| A-07 | Hard-coded prices | P3 | AC-3 price-change test |
| A-08 | No durable artifacts | P5 | run-dir tests |
| A-09 | Stringly-typed status | P3 | enum + exhaustive test |
| A-10 | Over-constrained regression | P3 | assert rules/signature, not the literal step list |
| A-11 | One-button dashboard | P7 | AppTest + manual checklist |
| A-12 | Findings not exportable | P5 | round-trip test |
| A-13 | Action log mutates previous record | P2 | executor logs commit step |
| A-14 | Deprecated Streamlit arg | P7 | lint/render smoke |
| A-15 | No logging | P2 (run-scoped logger) | report contains step failure detail |
| A-16 | Raw browser-missing error | P6/P7 | `doctor` + friendly UI message |
| A-17 | Duplicated config | P1 | single `Settings` import |
| A-18 | Totals not `aria-live` | not planned | documented; demo fixture deliberately minimal |

## 3. Assumptions

1. Python 3.11+ is available and the user can create a venv (verified locally: 3.11.9).
2. Chromium can be downloaded once (`playwright install chromium`).
3. The bundled demo remains the canonical target; no external site is required.
4. Only one run happens at a time; concurrency is out of scope.
5. The seeded defect must never be fixed — tests assert the *finding*, not correct behavior.
6. No secrets or paid APIs are available, so any LLM work must be optional and mocked in tests.

## 4. Open questions for the owner

1. Is the nested folder intentional (e.g. a GitHub zip extraction), or should it be flattened?
2. Should `.bugsafari/runs/` survive phase completion in your working copy, or be cleaned?
3. Any constraint on adding `ruff`/`mypy` as dev-only dependencies?
4. Is a Streamlit-only UI acceptable for the hackathon demo, or is a shareable HTML report
   needed?
