# Architecture — Current and Target

## 1. Current structure (as delivered)

```
app/dashboard.py ──► bugsafari.engine.explorer ──► demo_app.app (Flask)
        │                     │
        │                     ├──► bugsafari.browser.controller ──► Playwright
        │                     ├──► bugsafari.detection.invariants
        │                     └──► bugsafari.reporting.models
        └──► bugsafari.reporting.reporter
```

Runtime sequence: the dashboard calls `run_demo_exploration()`, which starts Flask on an
ephemeral port (`make_server(host, 0, ...)`), waits for readiness, launches headless
Chromium, runs three controller calls, reads `[data-testid="total"]`, screenshots, checks the
invariant, and returns a `RunResult`. The UI renders status, action table, finding, and
screenshot from that object.

**The flaw:** arrows point one way only by name. In reality `bugsafari/` imports
`app.config` and `demo_app.app`, so the "framework" depends on one fixture, and the target
is not pluggable.

## 2. Target structure

```
   entry points                  bugsafari (core)                collaborators
   ────────────                  ────────────────                ─────────────
   CLI  python -m bugsafari ─┐
   Streamlit dashboard ──────┼──►  engine/runner.py  ──►  browser/  (Playwright, Snapshot)
   pytest / CI ──────────────┘          │                   │
                                        │                   ▼
   scenarios/*.json ────────────────────┤              detection/ (rules, pure)
                                        │                   │
                                        ▼                   ▼
                                   reporting/  ◄──────  Finding / Run
                                (store, markdown, json)

   planner/  ──► produces Step lists for engine/runner.py   (optional; scripted default)
   demo_app/ ──► the application under test  (imports nothing from bugsafari or app)
```

Hard rules:

| Rule | Rationale |
|------|-----------|
| `bugsafari/*` must not import `app` or `demo_app` | Keeps the engine usable against any URL |
| `demo_app/*` must not import `bugsafari` or `app` | A target must be independent of the tester |
| Targets are resolved through `TargetSpec`, never a direct import | Same code path for local and remote apps |
| Rules receive a `Snapshot`, never a live `Page` | Rules stay pure, fast, and unit-testable |
| The planner only produces `Step` objects | Swapping scripted → LLM changes no executor code |
| Artifacts are written under one configurable root | Reproducible, gitignore-able, path-independent |

## 3. Target file tree

```
scenarios/
  cart-total-quantity.json          # encodes today's hard-coded run
  internal-consistency.json         # price-free meta-invariant scenario
bugsafari/
  __main__.py                       # python -m bugsafari
  cli.py                            # argparse subcommands, exit codes
  config.py                         # Settings dataclass + env loading
  logging.py                        # run-scoped structured logger
  browser/
    controller.py                   # extended, timeout-aware
    snapshot.py                     # page → Snapshot extraction
  detection/
    invariants.py                   # money helpers (kept, hardened)
    rules.py                        # rule registry + built-in rules
    engine.py                       # evaluate(snapshot, specs) → findings
  engine/
    target.py                       # TargetSpec, managed local server
    executor.py                     # step registry, step outcomes
    minimizer.py                    # ddmin over steps
    runner.py                       # orchestrates one run end to end
  planner/
    base.py                         # Planner protocol
    scripted.py                     # replay scenario steps (default)
    seeded_random.py                # bounded exploration
    llm.py                          # optional, disabled without a key
  reporting/
    models.py                       # + Snapshot, Verdict, RunStatus enum
    store.py                        # run dirs, run.json, atomic writes
    reporter.py                     # markdown + json renderers
app/
  dashboard.py                      # run history, scenario picker, downloads
  config.py                         # thin re-export of bugsafari.config
tests/
  conftest.py                       # fixtures: settings, server, browser, tmp run dir
  unit/                             # no browser, milliseconds
  integration/                      # browser-backed
  cli/                              # subprocess smoke tests
```

## 4. Key contracts

### 4.1 Settings (`bugsafari/config.py`)

```python
@dataclass(frozen=True)
class Settings:
    target_url: str | None          # None → managed local demo
    demo_host: str                  # 127.0.0.1
    demo_port: int                  # 0 for standalone default 5000
    headless: bool                  # True
    action_timeout_ms: int          # 5_000
    run_timeout_s: int              # 120
    art_dir: Path                   # artifacts/
    runs_dir: Path                  # .bugsafari/runs/
    planner: str                    # "scripted"
    minimize: bool                  # True
    max_minimize_attempts: int      # 40

def load_settings(env: Mapping[str, str] | None = None) -> Settings: ...
```

Precedence: explicit CLI flag > environment variable (`BUGSAFARI_*`) > default.

### 4.2 Scenario data

```json
{
  "id": "cart-total-quantity",
  "name": "Quantity change keeps cart total in sync",
  "target": { "kind": "local_demo" },
  "steps": [
    { "action": "open" },
    { "action": "click", "target": "add-trail-mug" },
    { "action": "change_quantity", "target": "quantity-trail-mug", "value": "2" }
  ],
  "capture": ["total", "subtotal", "checkout-total", "line-total-trail-mug"],
  "invariants": [
    { "rule": "internal_totals_consistent" },
    { "rule": "cart_total_matches_quantities" }
  ]
}
```

Loaded and validated by `scenarios/loader.py`; unknown actions or rules fail at load time
with a message naming the field, never at step 3 of a browser run.

### 4.3 Snapshot (pure data)

```python
@dataclass(frozen=True)
class CatalogItem:
    id: str
    name: str
    price_cents: int

@dataclass(frozen=True)
class Snapshot:
    url: str
    catalog: dict[str, CatalogItem]   # from [data-product][data-price]
    cart: dict[str, int]              # test id → quantity read from inputs
    texts: dict[str, str]             # test id → inner text, per "capture"
    row_count: int

    def cents(self, test_id: str) -> int | None: ...   # unparseable → None
```

Extraction (`browser/snapshot.py`) reads the DOM once. Every rule is then a pure function
`Snapshot -> Finding | None`, so the entire detection layer is tested without a browser.

### 4.4 Rules

| Rule id | Assertion | Catches seeded bug? |
|---------|-----------|---------------------|
| `internal_totals_consistent` | total == subtotal == checkout total | Yes, no prices needed |
| `cart_total_matches_quantities` | total == Σ price × qty | Yes |
| `line_total_matches_price_x_qty` | each line == price × its qty | No (line is correct) |
| `subtotal_equals_total` | two aggregates agree | Yes |
| `cart_empty_has_zero_total` | empty cart ⇒ $0.00 | Guards regressions |

Malformed money is a `RuleError`, reported as `execution_error`, never a fabricated finding.
A rule that cannot evaluate is not a bug.

### 4.5 Executor

```python
class Executor:
    def __init__(self, controller, settings): ...
    def run(self, steps: list[Step]) -> ExecutionResult: ...
```

- Action registry: `open, click, fill, change_quantity, press, select, wait_visible, read`.
- Each step gets `action_timeout_ms`; the whole run gets `run_timeout_s`.
- Failure yields `StepError(step_index, action, target, message)`; the log keeps every step
  attempted, including the failing one, with `result="failed: ..."`.
- Steps are never silently skipped.

### 4.6 Minimizer

Target signature = `(rule_id, expected, actual)`. `ddmin` over the step list; each candidate
is replayed in a fresh controlled environment; the candidate is kept only if the identical
signature still reproduces. Bounded by `max_minimize_attempts` and `run_timeout_s`.
Output: `original_steps`, `minimized_steps`, `attempts`, `reduction`.

### 4.7 Run store and report

```
.bugsafari/runs/<run-id>/
  run.json        # schema_version 1, status, scenario, steps, snapshot, findings, env
  report.md       # human report: summary, expected/actual, repro, evidence
  screenshot.png
  minimized.json  # only when minimization changed the sequence
```

`run-id` = `run-<UTC timestamp>-<6 hex>`, so runs sort chronologically and never collide.
Writes go to a temp dir then rename, so an interrupted run leaves no half-written report.
`artifacts/latest.png` is kept as a copy for backward compatibility with the README.

### 4.8 Planner

```python
class Planner(Protocol):
    name: str
    def plan(self, scenario: Scenario, snapshot: Snapshot) -> list[Step]: ...
```

- `scripted` (default): returns the scenario steps unchanged. Fully deterministic.
- `seeded_random`: reproducible exploration using `random.Random(seed)`; bounded action count.
- `llm` (optional): sends a compact page summary, receives a JSON step list, validates it
  against the same schema, and **falls back to scripted on any error**. Never required by
  tests or the demo; no key configured means cleanly unavailable, not a crash.

### 4.9 CLI

```
python -m bugsafari run --scenario cart-total-quantity [--url URL] [--headed]
                         [--no-minimize] [--json] [--report PATH]
python -m bugsafari scenarios list
python -m bugsafari runs list | show <run-id>
python -m bugsafari doctor          # python, browser, target checks
```

Exit codes: `0` passed, `1` bug detected, `2` execution error, `64` usage error.
The dashboard calls the same `runner.run_scenario()` service, so UI and CLI cannot diverge.

## 5. Dashboard changes

Single page becomes a three-region layout:

1. **Left:** scenario picker, target URL (blank = local demo), headless toggle, minimize
   toggle, *Run* button.
2. **Center:** status badge, finding card (rule, expected vs actual, details), minimized
   reproduction, full action table, screenshot.
3. **Right/bottom:** run history from `runs list` with timestamps and statuses; selecting a
   past run reloads its `run.json` without re-running the browser; download buttons for
   `report.md`, `run.json`, and the screenshot.

Because a run blocks, it executes in a worker thread with a progress placeholder; the UI
stays responsive and failures surface as a readable error card (including "Chromium not
installed — run `python -m playwright install chromium`").

## 6. Compatibility

`bugsafari.engine.explorer.run_demo_exploration(screenshot_path)` is retained as a thin
adapter over `runner.run_scenario(...)` returning the existing `RunResult` shape. This keeps
`tests/test_seeded_bug.py`, the README instructions, and any external caller working while
the internals move. It is scheduled for removal in M4 once the CLI is the documented path.
