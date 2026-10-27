"""Settings loading and validation."""

from pathlib import Path

import pytest

from bugsafari.config import PROJECT_ROOT, Settings, load_settings

pytestmark = pytest.mark.unit


def test_defaults_need_no_environment():
    settings = load_settings({})
    assert settings.target_url is None
    assert settings.demo_host == "127.0.0.1"
    assert settings.demo_port == 0
    assert settings.headless is True
    assert settings.planner == "scripted"
    assert settings.minimize is True
    assert settings.scenarios_dir == PROJECT_ROOT / "scenarios"
    assert isinstance(settings, Settings)


def test_environment_overrides_are_applied():
    settings = load_settings(
        {
            "BUGSAFARI_TARGET_URL": "http://127.0.0.1:5000",
            "BUGSAFARI_HEADLESS": "false",
            "BUGSAFARI_ACTION_TIMEOUT_MS": "1500",
            "BUGSAFARI_PLANNER": "Seeded_Random",
            "BUGSAFARI_MINIMIZE": "0",
            "BUGSAFARI_SEED": "7",
        }
    )
    assert settings.target_url == "http://127.0.0.1:5000"
    assert settings.headless is False
    assert settings.action_timeout_ms == 1500
    assert settings.planner == "seeded_random"
    assert settings.minimize is False
    assert settings.seed == 7


def test_relative_output_paths_resolve_against_project_root():
    settings = load_settings({"BUGSAFARI_RUNS_DIR": ".bugsafari/runs", "BUGSAFARI_ARTIFACT_DIR": "artifacts"})
    assert settings.runs_dir == PROJECT_ROOT / ".bugsafari" / "runs"
    assert settings.artifact_dir == PROJECT_ROOT / "artifacts"
    assert settings.runs_dir.is_absolute()
    assert settings.artifact_dir.is_absolute()


def test_absolute_output_paths_are_kept(tmp_path: Path):
    settings = load_settings({"BUGSAFARI_RUNS_DIR": str(tmp_path / "runs")})
    assert settings.runs_dir == tmp_path / "runs"


@pytest.mark.parametrize(
    ("env", "needle"),
    [
        ({"BUGSAFARI_PLANNER": "magic"}, "must be one of"),
        ({"BUGSAFARI_HEADLESS": "maybe"}, "must be a boolean"),
        ({"BUGSAFARI_DEMO_PORT": "99999"}, "out of range"),
        ({"BUGSAFARI_ACTION_TIMEOUT_MS": "0"}, "must be positive"),
        ({"BUGSAFARI_RUN_TIMEOUT_S": "0"}, "must be positive"),
        ({"BUGSAFARI_MAX_MINIMIZE_ATTEMPTS": "0"}, "must be positive"),
        ({"BUGSAFARI_SEED": "abc"}, "must be an integer"),
    ],
)
def test_invalid_settings_fail_loudly(env, needle):
    with pytest.raises(ValueError, match=needle):
        load_settings(env)


def test_ensure_dirs_creates_output_directories(tmp_path: Path):
    settings = load_settings(
        {
            "BUGSAFARI_RUNS_DIR": str(tmp_path / "runs"),
            "BUGSAFARI_ARTIFACT_DIR": str(tmp_path / "artifacts"),
        }
    )
    settings.ensure_dirs()
    assert settings.runs_dir.is_dir()
    assert settings.artifact_dir.is_dir()
