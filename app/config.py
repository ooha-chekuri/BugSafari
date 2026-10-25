"""Shared application configuration."""

import os

DEMO_HOST = "127.0.0.1"
DEMO_PORT = int(os.environ.get("BUGSAFARI_PORT", "5000"))
SCREENSHOT_PATH = "artifacts/latest.png"
