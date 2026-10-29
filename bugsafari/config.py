"""Typed, environment-driven settings shared by every BugSafari entry point.

Precedence: explicit overrides (CLI flags) > environment variables > defaults.
Relative paths are resolved against the project root so that the tool behaves
the same regardless of the working directory it was launched from.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEMO_BASE_URL = "http://127.0.0.1:5000"

PLANNERS = ("scripted", "seeded_random", "llm")
_TRUE_VALUES = {"1", "true", "t", "yes", "y", "on"}
_FALSE_VALUES = {"0", "false", "f", "no", "n", "off"}


@dataclass(frozen=True)
class Settings:
    """All tunables in one immutable object."""

    target_url: str | None = None
    demo_host: str = "127.0.0.1"
    demo_port: int = 0
    demo_base_url: str = DEFAULT_DEMO_BASE_URL
    headless: bool = True
    browser_channel: str | None = None
    action_timeout_ms: int = 5_000
    run_timeout_s: int = 120
    artifact_dir: Path = PROJECT_ROOT / "artifacts"
    runs_dir: Path = PROJECT_ROOT / ".bugsafari" / "runs"
    scenarios_dir: Path = PROJECT_ROOT / "scenarios"
    planner: str = "scripted"
    seed: int = 0
    minimize: bool = True
    max_minimize_attempts: int = 40
    small_font_px: float = 12.0

    def with_overrides(self, **changes: object) -> Settings:
        """Return a copy with the given fields replaced (used by CLI flags)."""
        return replace(self, **changes)  # type: ignore[arg-type]

    def ensure_dirs(self) -> None:
        """Create the output directories if they do not exist yet."""
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)


def _flag(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(f"{name} must be a boolean value, got {raw!r}")


def _integer(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


def _decimal(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw.strip())
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc


def _path(env: Mapping[str, str], name: str, default: Path) -> Path:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    candidate = Path(raw.strip()).expanduser()
    return candidate if candidate.is_absolute() else (PROJECT_ROOT / candidate)


def _text(env: Mapping[str, str], name: str, default: str | None) -> str | None:
    raw = env.get(name)
    if raw is None:
        return default
    stripped = raw.strip()
    return stripped or None


def _lower(env: Mapping[str, str], name: str, default: str | None = None) -> str | None:
    value = _text(env, name, default)
    return value.lower() if value else None


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Build settings from environment variables, validating everything eagerly."""
    source = os.environ if env is None else env
    settings = Settings(
        target_url=_text(source, "BUGSAFARI_TARGET_URL", None),
        demo_host=_text(source, "BUGSAFARI_DEMO_HOST", "127.0.0.1") or "127.0.0.1",
        demo_port=_integer(source, "BUGSAFARI_DEMO_PORT", 0),
        demo_base_url=(
            _text(source, "BUGSAFARI_DEMO_BASE_URL", DEFAULT_DEMO_BASE_URL)
            or DEFAULT_DEMO_BASE_URL
        ),
        headless=_flag(source, "BUGSAFARI_HEADLESS", True),
        browser_channel=_lower(source, "BUGSAFARI_BROWSER_CHANNEL"),
        action_timeout_ms=_integer(source, "BUGSAFARI_ACTION_TIMEOUT_MS", 5_000),
        run_timeout_s=_integer(source, "BUGSAFARI_RUN_TIMEOUT_S", 120),
        artifact_dir=_path(source, "BUGSAFARI_ARTIFACT_DIR", Settings.artifact_dir),
        runs_dir=_path(source, "BUGSAFARI_RUNS_DIR", Settings.runs_dir),
        scenarios_dir=_path(source, "BUGSAFARI_SCENARIOS_DIR", Settings.scenarios_dir),
        planner=(_text(source, "BUGSAFARI_PLANNER", "scripted") or "scripted").lower(),
        seed=_integer(source, "BUGSAFARI_SEED", 0),
        minimize=_flag(source, "BUGSAFARI_MINIMIZE", True),
        max_minimize_attempts=_integer(source, "BUGSAFARI_MAX_MINIMIZE_ATTEMPTS", 40),
        small_font_px=_decimal(source, "BUGSAFARI_SMALL_FONT_PX", 12.0),
    )
    _validate(settings)
    return settings


def _validate(settings: Settings) -> None:
    if not 0 <= settings.demo_port <= 65_535:
        raise ValueError(f"BUGSAFARI_DEMO_PORT out of range: {settings.demo_port}")
    if settings.action_timeout_ms <= 0:
        raise ValueError("BUGSAFARI_ACTION_TIMEOUT_MS must be positive")
    if settings.run_timeout_s <= 0:
        raise ValueError("BUGSAFARI_RUN_TIMEOUT_S must be positive")
    if settings.max_minimize_attempts <= 0:
        raise ValueError("BUGSAFARI_MAX_MINIMIZE_ATTEMPTS must be positive")
    if settings.small_font_px <= 0:
        raise ValueError("BUGSAFARI_SMALL_FONT_PX must be positive")
    if settings.planner not in PLANNERS:
        raise ValueError(
            f"BUGSAFARI_PLANNER must be one of {', '.join(PLANNERS)}; got {settings.planner!r}"
        )
    if settings.run_timeout_s * 1000 < settings.action_timeout_ms:
        raise ValueError("BUGSAFARI_RUN_TIMEOUT_S must be at least the action timeout")
