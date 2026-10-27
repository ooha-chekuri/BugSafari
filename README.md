# BugSafari

**Autonomous Web Bug Detection and Reproducible Browser Testing**

BugSafari is a browser-testing project designed to explore web applications, detect invariant violations, verify reproducibility, and generate actionable bug reports.

## Features

- **Browser automation:** Interacts with web applications using Playwright.
- **Invariant-based detection:** Checks application behavior against defined rules.
- **Scenario-driven testing:** Runs repeatable test scenarios from JSON configuration files.
- **Bug reporting:** Records violated rules, expected and actual values, and reproduction steps.
- **Replay verification:** Re-runs a scenario to check whether a detected issue can be reproduced.
- **Reproduction minimization:** Attempts to find a shorter sequence of actions that preserves a finding.
- **Dashboard:** Provides a Streamlit interface for selecting scenarios, running tests, viewing results, and exporting JSON reports.
- **Test suite:** Includes automated tests for core functionality and supporting components.

## Project Structure

```text
BugSafari/
├── app/
│   ├── config.py
│   └── dashboard.py
├── bugsafari/
│   ├── browser/
│   ├── detection/
│   ├── engine/
│   ├── reporting/
│   └── scenarios/
├── demo_app/
│   ├── app.py
│   └── templates/
├── scenarios/
├── tests/
├── conftest.py
├── pyproject.toml
└── requirements-dev.txt
```

## Requirements

- Python 3.11 or a compatible version supported by the project
- Git
- A supported browser environment for Playwright
- Windows, macOS, or Linux

## Installation

Clone the repository:

```bash
git clone https://github.com/ooha-chekuri/BugSafari.git
cd BugSafari
```

Create and activate a virtual environment.

**Windows PowerShell:**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install the project dependencies:

```powershell
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
```

## Run the Dashboard

```powershell
python -m streamlit run app/dashboard.py
```

Open the local URL displayed in the terminal.

Select a scenario and click **Run Demo Test** to inspect the browser actions and results.

## Run Tests

```powershell
python -m pytest -q
```

## Scenario Configuration

Test scenarios are defined using JSON files in the `scenarios/` directory. A scenario specifies the target application, browser actions, captured values, and invariants to evaluate.

Available scenarios include:

- `cart-remove-total`
- `cart-total-quantity`
- `internal-consistency`

## Reports and Evidence

BugSafari can present detected findings and reproduction instructions in the dashboard and export a JSON bug report. Depending on the run, reports can include browser actions, replay-verification status, minimization diagnostics, and screenshot evidence.

## Current Status

The project is under active development. Run the automated test suite before accepting changes or preparing a release. Detection results depend on the scenario and the invariants evaluated during each run.

## Contributors

- Ooha Chekuri
- Hari Kowshik

## License

Add the project's chosen license before distributing it publicly.
