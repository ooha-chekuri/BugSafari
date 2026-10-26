"""Data models shared by the explorer, detector, and dashboard."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ActionRecord:
    action: str
    target: str
    value: str | None
    result: str


@dataclass
class Finding:
    rule: str
    expected: str
    actual: str
    reproduction_steps: list[ActionRecord]
    status: str = "confirmed_violation"
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunResult:
    status: str
    actions: list[ActionRecord] = field(default_factory=list)
    finding: Finding | None = None
    screenshot: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "actions": [asdict(item) for item in self.actions],
                "finding": self.finding.to_dict() if self.finding else None,
                "screenshot": self.screenshot, "error": self.error}
