# BugSafari

BugSafari is an Agentic AI hackathon project for exploring web applications, checking explicit behavior rules, and producing reproducible bug reports. The problem it targets is that failures caused by unexpected combinations of actions can be difficult to find and reproduce manually.

## First implementation

This first vertical slice runs a deterministic Playwright scenario against a local Flask e-commerce demo. It adds a Trail Mug, changes its quantity to two, reads the displayed total, and checks it against a Python invariant. The shop intentionally leaves the displayed total at `$18.00` after quantity changes, although the correct total is `$36.00`. Line item quantity and line total update; the stale subtotal, total, and checkout total are the isolated seeded defect. Product addition and removal work normally.

The expected behavior is that subtotal, total, and checkout summary reflect the sum of each product price multiplied by its quantity. The faulty behavior is that these totals remain at their previous value after a quantity change. Detection is a confirmed invariant violation; browser or test failures are separately represented as execution errors.

## Architecture

- `demo_app/`: local Flask shop and its deliberately seeded frontend defect.
- `bugsafari/browser/`: Playwright controller with structured action recording.
- `bugsafari/engine/`: bounded deterministic scenario and managed local server.
- `bugsafari/detection/`: explicit integer-cent invariant checks.
- `bugsafari/reporting/`: finding and run data models plus reproduction formatting.
- `app/dashboard.py`: Streamlit interface that invokes the actual browser workflow.
- `tests/`: unit checks and a browser-backed seeded-bug regression.
- `artifacts/`: screenshot output (generated files are ignored by Git).

Actions are represented as records so a future planner can supply a sequence without changing the browser controller or detector. The current planner is only a fixed scenario. Automatic failure minimization, autonomous or LLM-driven exploration, and generated regression tests are future work. No API key is required.

## Prerequisites and installation

Use Python 3.11 or newer. From the project root:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
```

The browser-backed test starts and stops its own local Flask server on an available local port, so it can run while the standalone demo is open. It writes a screenshot under `artifacts/` when the test succeeds.

## Run the applications

Start the demo shop in one terminal:

```powershell
python -m demo_app.app
```

Open <http://127.0.0.1:5000>.

Start the dashboard in another terminal:

```powershell
streamlit run app/dashboard.py
```

Use **Run demo test** to launch the actual browser scenario and view its action log, result, finding, reproduction steps, and screenshot. A detected seeded defect is a successful BugSafari detection run; an inability to execute the browser is reported as an execution error.

## Tests

```powershell
pytest
```

`tests/test_invariants.py` checks money handling and correct totals. `tests/test_seeded_bug.py` runs Chromium against the demo and verifies the mismatch and recorded action history. Install the Playwright Chromium browser before running the latter.

## Next milestones

1. Add scenario definitions and configurable action sequences, plus more independently seeded invariants.
2. Implement failure minimization that removes actions while preserving a confirmed finding.
3. Add a pluggable planner interface and evaluate an optional LLM planner against the deterministic baseline.
