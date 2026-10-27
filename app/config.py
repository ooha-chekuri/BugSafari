"""Compatibility shim.

Configuration now lives in :mod:`bugsafari.config`; this module only re-exports
the constants the original dashboard and explorer imported, so existing callers
keep working during the migration.
"""

from bugsafari.config import PROJECT_ROOT, load_settings

_settings = load_settings()

DEMO_HOST = _settings.demo_host
# Standalone demo port. Managed runs bind port 0 and never use this value.
DEMO_PORT = 5000
SCREENSHOT_PATH = str(_settings.artifact_dir / "latest.png")

__all__ = ["DEMO_HOST", "DEMO_PORT", "PROJECT_ROOT", "SCREENSHOT_PATH"]
