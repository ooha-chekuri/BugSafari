
"""Data models shared by the executor, detector, reporter, and dashboard.

Everything here is plain data so it can be serialized, compared, and unit
tested without a browser.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

RUN_SCHEMA_VERSION = 1


class RunStatus(str, Enum):
    """Outcome of one browser run."""

    PASSED = "passed"
    BUG_DETECTED = "bug_detected"
    EXECUTION_ERROR = "execution_error"

    @classmethod
    def coerce(cls, value: RunStatus | str) -> RunStatus:
        if isinstance(value, cls):
            return value
        return cls(str(value))

    def __str__(self) -> str:
        return self.value


@dataclass
class ActionRecord:
    """One attempted browser interaction, in the order it happened."""

    action: str
    target: str
    value: str | None
    result: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionRecord:
        return cls(
            action=str(data["action"]),
            target=str(data["target"]),
            value=None if data.get("value") is None else str(data["value"]),
            result=str(data["result"]),
        )


@dataclass(frozen=True)
class CatalogItem:
    """A product as advertised by the page under test."""

    id: str
    name: str
    price_cents: int


@dataclass(frozen=True)
class Snapshot:
    """Captured page state used by detection rules."""

    url: str
    catalog: dict[str, CatalogItem] = field(default_factory=dict)
    cart: dict[str, int] = field(default_factory=dict)
    texts: dict[str, str] = field(default_factory=dict)
    line_totals: dict[str, str] = field(default_factory=dict)
    row_count: int = 0

    def text(self, test_id: str, default: str = "") -> str:
        return self.texts.get(test_id, default)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "catalog": {
                key: asdict(item) for key, item in self.catalog.items()
            },
            "cart": dict(self.cart),
            "texts": dict(self.texts),
            "line_totals": dict(self.line_totals),
            "row_count": self.row_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Snapshot:
        catalog = {
            key: CatalogItem(
                id=str(item.get("id", key)),
                name=str(item.get("name", key)),
                price_cents=int(item.get("price_cents", 0)),
            )
            for key, item in dict(data.get("catalog", {})).items()
        }
        return cls(
            url=str(data.get("url", "")),
            catalog=catalog,
            cart={
                str(key): int(value)
                for key, value in dict(data.get("cart", {})).items()
            },
            texts={
                str(key): str(value)
                for key, value in dict(data.get("texts", {})).items()
            },
            line_totals={
                str(key): str(value)
                for key, value in dict(
                    data.get("line_totals", {})
                ).items()
            },
            row_count=int(data.get("row_count", 0)),
        )


@dataclass
class Finding:
    """A confirmed rule violation together with its reproduction."""

    rule: str
    expected: str
    actual: str
    reproduction_steps: list[ActionRecord] = field(default_factory=list)
    status: str = "confirmed_violation"
    details: str = ""
    severity: str = "major"

    def signature(self) -> tuple[str, str, str]:
        """Identity used to verify that a finding persists."""
        return (self.rule, self.expected, self.actual)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Finding:
        return cls(
            rule=str(data["rule"]),
            expected=str(data["expected"]),
            actual=str(data["actual"]),
            reproduction_steps=[
                ActionRecord.from_dict(item)
                for item in data.get("reproduction_steps", [])
            ],
            status=str(data.get("status", "confirmed_violation")),
            details=str(data.get("details", "")),
            severity=str(data.get("severity", "major")),
        )


@dataclass
class RunResult:
    """Public result of a run, kept compatible with the dashboard API."""

    status: RunStatus
    actions: list[ActionRecord] = field(default_factory=list)
    finding: Finding | None = None
    screenshot: str | None = None
    error: str | None = None
    run_id: str | None = None
    minimized_actions: list[ActionRecord] | None = None
    minimization_stats: dict[str, Any] | None = None
    findings: list[Finding] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.status = RunStatus.coerce(self.status)
        if self.finding is not None and not self.findings:
            self.findings = [self.finding]

    @property
    def detected(self) -> bool:
        return self.status is RunStatus.BUG_DETECTED

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": RUN_SCHEMA_VERSION,
            "run_id": self.run_id,
            "status": self.status.value,
            "actions": [action.to_dict() for action in self.actions],
            "minimized_actions": (
                None
                if self.minimized_actions is None
                else [
                    action.to_dict()
                    for action in self.minimized_actions
                ]
            ),
            "minimization_stats": self.minimization_stats,
            "finding": (
                self.finding.to_dict() if self.finding else None
            ),
            "findings": [
                finding.to_dict() for finding in self.findings
            ],
            "screenshot": self.screenshot,
            "error": self.error,
        }


@dataclass
class StoredRun:
    """Persisted run, reloadable without launching a browser."""

    run_id: str
    scenario_id: str
    scenario_name: str
    status: RunStatus
    started_at: str
    duration_s: float
    actions: list[ActionRecord] = field(default_factory=list)
    minimized_actions: list[ActionRecord] | None = None
    findings: list[Finding] = field(default_factory=list)
    error: str | None = None
    snapshot: Snapshot | None = None
    environment: dict[str, str] = field(default_factory=dict)
    screenshot: str | None = None
    report: str = ""

    def __post_init__(self) -> None:
        self.status = RunStatus.coerce(self.status)

    @property
    def primary_finding(self) -> Finding | None:
        return self.findings[0] if self.findings else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": RUN_SCHEMA_VERSION,
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "status": self.status.value,
            "started_at": self.started_at,
            "duration_s": round(self.duration_s, 3),
            "actions": [action.to_dict() for action in self.actions],
            "minimized_actions": (
                None
                if self.minimized_actions is None
                else [
                    action.to_dict()
                    for action in self.minimized_actions
                ]
            ),
            "findings": [
                finding.to_dict() for finding in self.findings
            ],
            "error": self.error,
            "snapshot": (
                self.snapshot.to_dict() if self.snapshot else None
            ),
            "environment": dict(self.environment),
            "screenshot": self.screenshot,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoredRun:
        return cls(
            run_id=str(data["run_id"]),
            scenario_id=str(data["scenario_id"]),
            scenario_name=str(data["scenario_name"]),
            status=RunStatus.coerce(data["status"]),
            started_at=str(data["started_at"]),
            duration_s=float(data.get("duration_s", 0)),
            actions=[
                ActionRecord.from_dict(item)
                for item in data.get("actions", [])
            ],
            minimized_actions=(
                None
                if data.get("minimized_actions") is None
                else [
                    ActionRecord.from_dict(item)
                    for item in data["minimized_actions"]
                ]
            ),
            findings=[
                Finding.from_dict(item)
                for item in data.get("findings", [])
            ],
            error=(
                None if data.get("error") is None
                else str(data["error"])
            ),
            snapshot=(
                None
                if data.get("snapshot") is None
                else Snapshot.from_dict(data["snapshot"])
            ),
            environment={
                str(key): str(value)
                for key, value in dict(
                    data.get("environment", {})
                ).items()
            },
            screenshot=(
                None
                if data.get("screenshot") is None
                else str(data["screenshot"])
            ),
        )
