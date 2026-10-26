# Testing Strategy

Principle: the fast suite must never need a browser. Only integration tests launch
Chromium, and there are as few of those as possible.

## 1. Layers

| Layer | Location | Browser | Target runtime | Purpose |
|-------|----------|---------|----------------|---------|
| Unit | `tests/unit/` | no | < 5 s total | Pure logic: money, rules, loader, executor (stub page), minimizer (injected reproducer), store, report rendering, planner |
| Integration | `tests/integration/` | yes | < 90 s total | Real Flask + real Chromium: seeded-bug regression, external URL, minimization, snapshot extraction |
| CLI | `tests/cli/` | only where noted | < 20 s | `subprocess` invocations, exit codes, output shape, artifact creation |
| UI | `tests/integration/test_dashboard_apptest.py` | no | < 10 s | `streamlit.testing.v1.AppTest` smoke: renders, controls present, history empty state |

## 2. Test matrix

| File | Proves | Marker |
|------|--------|--------|
| `unit/test_money.py` | `parse_money`/`format_money` incl. `""`, `"$"`, `"$1,234.50"`, `"18.5"`, `".50"`, negatives | unit |
| `unit/test_scenario_loader.py` | valid load, unknown action, unknown rule, missing field, bad JSON | unit |
| `unit/test_executor.py` | each action dispatches, timeouts, `StepError` carries index, failed step is recorded | unit |
| `unit/test_snapshot.py` | extraction from saved HTML fixture (no browser needed if parsing helper is split) | unit |
| `unit/test_rules.py` | one passing + one failing case per rule, malformed money → `RuleError`, unknown item → `RuleError` | unit |
| `unit/test_minimizer.py` | redundant steps removed, signature stable, attempt budget respected, non-reproducible candidate rejected | unit |
| `unit/test_store.py` | id uniqueness/order, atomic write leaves nothing on failure, round-trip equality | unit |
| `unit/test_report.py` | golden `report.md` and `run.json` for a fixed fixture run | unit |
| `unit/test_planner.py` | scripted returns scenario steps, seeded random reproducible, LLM fallback on error/absence | unit |
| `unit/test_import_guard.py` | no `bugsafari` module imports `app`/`demo_app`; no `demo_app` imports `bugsafari` | unit |
| `integration/test_seeded_bug.py` | `$36.00` expected vs `$18.00` actual, screenshot written | integration |
| `integration/test_external_target.py` | `--url` against a manually started demo detects the bug | integration |
| `integration/test_minimize_seeded.py` | minimization on the real 3-step scenario keeps the signature | integration |
| `integration/test_determinism.py` | same scenario 5× → identical status, rule, expected, actual, step actions | integration |
| `integration/test_dashboard_apptest.py` | dashboard renders and wires the run button | integration |
| `cli/test_cli.py` | `--help`, `scenarios list`, `doctor`, closed-port run → exit 2 | cli |
| `cli/test_cli_run.py` | real run → exit 1, run directory exists, `runs list` shows it | cli + integration |

## 3. Fixtures (`tests/conftest.py`)

| Fixture | Scope | Behavior |
|---------|-------|----------|
| `settings` | function | `Settings` with `tmp_path` artifact dirs, short timeouts (2 s) so failures are fast |
| `demo_server` | function | `managed_local_server()` on port 0, yields base URL, always shuts down |
| `browser` | session | One Chromium instance for the whole integration session; contexts per test |
| `page` | function | Fresh context + page, closed after the test |
| `sample_snapshot` | function | A `Snapshot` representing the buggy post-quantity state, built from data |
| `fixed_run` | function | A deterministic `Run` object for golden-file rendering |
| `blocked_socket` | function | Monkeypatches `socket.socket` to fail — proves the LLM planner never dials out |

Rules for fixtures: no fixture may write outside `tmp_path`; no fixture may depend on the
process CWD; every server/browser fixture cleans up in `finally`.

## 4. Determinism rules

1. No `datetime.now()` inside logic — inject a clock or generate the id at the boundary.
2. Randomness only via `random.Random(seed)`; the seed is part of the run record.
3. Ephemeral ports (`0`) everywhere, never a fixed port in tests.
4. No sleeps for synchronization; readiness probes with deadlines (the pattern already used
   in `explorer.py:24-34`).
5. No wall-clock assertions; assert budgets loosely (`< settings.run_timeout_s`).
6. Golden files store a normalized report (ids and timestamps replaced by placeholders).

## 5. Commands

```powershell
# fast loop
pytest -m "not integration"

# everything
pytest

# one layer
pytest tests/integration

# coverage of the core
pytest --cov=bugsafari --cov-report=term-missing

# lint
ruff check .

# end-to-end sanity
python -m bugsafari run --scenario cart-total-quantity
```

## 6. CI (`.github/workflows/ci.yml`)

| Job | Steps | Gate |
|-----|-------|------|
| `lint` | checkout, Python 3.11, `pip install -r requirements-dev.txt`, `ruff check .` | required |
| `unit` | install runtime deps, `pytest -m "not integration"` | required, must stay under 60 s |
| `integration` | install deps, `playwright install --with-deps chromium`, `pytest -m integration` | required on Linux |
| `cli-smoke` | `python -m bugsafari doctor`, `... scenarios list` | required |
| `artifacts` | upload `.bugsafari/runs/**` and the failure screenshot | on failure |

Caching: pip cache plus Playwright's browser cache keyed on the Playwright version.

## 7. Flake policy

- A repeatedly failing browser test is **quarantined with an issue**, not given retries.
  Retries hide the non-determinism this project exists to demonstrate.
- The only tolerated non-determinism is timing; assertions must not encode it.
- If `test_seeded_bug` fails, treat it as a product regression first, a flake second.

## 8. What is deliberately not tested

- Streamlit's own rendering internals beyond the AppTest smoke.
- Real LLM provider responses (mocked transport only).
- Cross-browser behavior (Chromium only, matching the README).
- The intentionally buggy `shop.html` behavior as "correct" — it is asserted as a *finding*,
  never as desired behavior.
