"""Execute validated steps, recording every attempt including failures."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import TYPE_CHECKING

from bugsafari.config import Settings
from bugsafari.scenarios.model import Step

if TYPE_CHECKING:
    from bugsafari.browser.controller import BrowserController


class StepError(RuntimeError):
    """A single step could not be completed."""

    def __init__(self, index: int, step: Step, message: str):
        self.index = index
        self.step = step
        self.message = message
        super().__init__(f"step {index + 1} ({step.describe()}): {message}")


@dataclass(frozen=True)
class StepOutcome:
    index: int
    step: Step
    ok: bool
    duration_ms: int
    error: str | None = None


@dataclass
class ExecutionResult:
    outcomes: list[StepOutcome] = field(default_factory=list)
    error: StepError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class Executor:
    """Dispatch scenario steps to the controller with a bounded total runtime."""

    def __init__(
        self,
        controller: BrowserController,
        settings: Settings,
        url: str,
    ):
        self.controller = controller
        self.settings = settings
        self.url = url

    def run(self, steps: list[Step] | tuple[Step, ...]) -> ExecutionResult:
        result = ExecutionResult()
        deadline = monotonic() + self.settings.run_timeout_s
        for index, step in enumerate(steps):
            started = monotonic()
            try:
                if monotonic() > deadline:
                    raise StepError(
                        index,
                        step,
                        f"run timeout of {self.settings.run_timeout_s}s exceeded",
                    )
                self._perform(step)
            except StepError as exc:
                result.error = exc
                result.outcomes.append(self._outcome(index, step, started, exc.message))
                self._record_failure(step, exc.message)
                break
            except Exception as exc:  # noqa: BLE001 - normalized into a step error
                message = f"{type(exc).__name__}: {_first_line(exc)}"
                result.error = StepError(index, step, message)
                result.outcomes.append(self._outcome(index, step, started, message))
                self._record_failure(step, message)
                break
            result.outcomes.append(self._outcome(index, step, started))
        return result

    def _perform(self, step: Step) -> None:
        action = step.action
        target = step.target or ""
        if action == "open":
            self.controller.open(self.url)
        elif action == "click":
            self.controller.click(target)
        elif action == "fill":
            self.controller.fill(target, step.value or "")
        elif action == "change_quantity":
            self.controller.change_quantity(target, step.value or "")
        elif action == "press":
            self.controller.press(target, step.value or "Enter")
        elif action == "select":
            self.controller.select(target, step.value or "")
        elif action == "wait_visible":
            self.controller.wait_visible(target)
        elif action == "read":
            self.controller.read(target)
            self.controller.record("read", target, None, "captured")
        else:  # pragma: no cover - the loader rejects unknown actions first
            raise ValueError(f"unsupported action {action!r}")

    def _record_failure(self, step: Step, message: str) -> None:
        self.controller.record(
            step.action, step.target or self.url, step.value, f"failed: {message}"
        )

    @staticmethod
    def _outcome(
        index: int, step: Step, started: float, error: str | None = None
    ) -> StepOutcome:
        return StepOutcome(
            index=index,
            step=step,
            ok=error is None,
            duration_ms=int((monotonic() - started) * 1000),
            error=error,
        )


def _first_line(exc: BaseException) -> str:
    text = str(exc).strip().splitlines()
    return text[0] if text else exc.__class__.__name__
