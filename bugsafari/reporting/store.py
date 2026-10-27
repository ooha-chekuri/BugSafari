"""Durable run storage: one directory per run, written atomically."""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from bugsafari.reporting.models import RunResult, Snapshot, StoredRun
from bugsafari.reporting.reporter import render_json, render_markdown
from bugsafari.scenarios.model import Scenario

RUN_JSON = "run.json"
REPORT_MD = "report.md"
SCREENSHOT = "screenshot.png"
MINIMIZED_JSON = "minimized.json"

_RUN_ID = re.compile(r"^run-\d{8}T\d{6}Z-[0-9a-f]{6}$")


class StoreError(RuntimeError):
    """A run could not be written or read."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_run_id(moment: datetime | None = None) -> str:
    """Return a sortable, collision-resistant run id."""
    stamp = (moment or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    return f"run-{stamp}-{uuid4().hex[:6]}"


class RunStore:
    """Read and write run directories beneath ``runs_dir``."""

    def __init__(self, runs_dir: str | Path):
        self.runs_dir = Path(runs_dir)

    def run_dir(self, run_id: str) -> Path:
        if not _RUN_ID.match(run_id):
            raise StoreError(f"invalid run id: {run_id!r}")
        return self.runs_dir / run_id

    def save(
        self,
        *,
        result: RunResult,
        scenario: Scenario,
        snapshot: Snapshot | None,
        environment: dict[str, str],
        started_at: str,
        duration_s: float,
        screenshot_path: str | Path | None = None,
    ) -> StoredRun:
        """Persist a completed run, including its rendered report."""
        run_id = result.run_id or new_run_id()
        findings = list(result.findings)
        if not findings and result.finding is not None:
            findings = [result.finding]
        has_screenshot = bool(screenshot_path) and Path(str(screenshot_path)).is_file()

        stored = StoredRun(
            run_id=run_id,
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            status=result.status,
            started_at=started_at,
            duration_s=duration_s,
            actions=list(result.actions),
            minimized_actions=(
                None
                if result.minimized_actions is None
                else list(result.minimized_actions)
            ),
            findings=findings,
            error=result.error,
            snapshot=snapshot,
            environment=dict(environment),
            screenshot=SCREENSHOT if has_screenshot else None,
        )
        stored.report = render_markdown(stored)
        self._write(stored, Path(str(screenshot_path)) if has_screenshot else None)
        return stored

    def load(self, run_id: str) -> StoredRun:
        directory = self.run_dir(run_id)
        if not directory.is_dir():
            raise StoreError(f"no stored run named {run_id!r} in {self.runs_dir}")
        return self._read(directory)

    def exists(self, run_id: str) -> bool:
        try:
            return self.run_dir(run_id).is_dir()
        except StoreError:
            return False

    def list_runs(self) -> list[StoredRun]:
        """Return stored runs, newest first, skipping unreadable directories."""
        if not self.runs_dir.is_dir():
            return []
        runs: list[StoredRun] = []
        for entry in sorted(self.runs_dir.iterdir(), reverse=True):
            if not entry.is_dir() or not (entry / RUN_JSON).is_file():
                continue
            try:
                runs.append(self._read(entry))
            except (OSError, ValueError, KeyError, StoreError):
                continue
        return runs

    def report_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / REPORT_MD

    def screenshot_path(self, run_id: str) -> Path | None:
        run = self.load(run_id)
        if not run.screenshot:
            return None
        candidate = self.run_dir(run_id) / run.screenshot
        return candidate if candidate.is_file() else None

    def _read(self, directory: Path) -> StoredRun:
        try:
            data = json.loads((directory / RUN_JSON).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise StoreError(f"{directory / RUN_JSON}: invalid JSON ({exc})") from exc
        run = StoredRun.from_dict(data)
        report_file = directory / REPORT_MD
        if report_file.is_file():
            run.report = report_file.read_text(encoding="utf-8")
        return run

    def _write(self, run: StoredRun, screenshot_path: Path | None) -> None:
        target = self.runs_dir / run.run_id
        if target.exists():
            raise StoreError(f"run directory already exists: {target}")
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".tmp-", dir=self.runs_dir))
        try:
            (staging / RUN_JSON).write_text(render_json(run), encoding="utf-8")
            (staging / REPORT_MD).write_text(run.report, encoding="utf-8")
            if run.minimized_actions is not None:
                payload = {
                    "run_id": run.run_id,
                    "actions": [action.to_dict() for action in run.minimized_actions],
                }
                (staging / MINIMIZED_JSON).write_text(
                    json.dumps(payload, indent=2) + "\n", encoding="utf-8"
                )
            if screenshot_path is not None and run.screenshot:
                shutil.copyfile(screenshot_path, staging / run.screenshot)
            staging.rename(target)
        except Exception as exc:  # noqa: BLE001 - cleanup then surface a store error
            shutil.rmtree(staging, ignore_errors=True)
            if isinstance(exc, StoreError):
                raise
            raise StoreError(f"could not save run {run.run_id}: {exc}") from exc
