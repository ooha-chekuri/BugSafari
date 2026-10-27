"""Resolve the URL a run should exercise and own the bundled demo server.

This module never imports the demo application. Entry points that want the
``local_demo`` target pass the Flask factory in, keeping the engine usable
against any site.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Thread
from time import monotonic, sleep
from urllib.request import urlopen

from werkzeug.serving import make_server

from bugsafari.config import Settings
from bugsafari.scenarios.model import TargetSpec

AppFactory = Callable[[], object]

READY_TIMEOUT_S = 5.0
READY_POLL_S = 0.05


class TargetError(RuntimeError):
    """The target could not be resolved or started."""


@dataclass(frozen=True)
class ResolvedTarget:
    url: str
    managed: bool = False


@contextmanager
def resolve_target(
    spec: TargetSpec,
    settings: Settings,
    app_factory: AppFactory | None = None,
) -> Iterator[ResolvedTarget]:
    """Yield the base URL for a scenario, starting the demo server when needed."""
    if spec.kind == "url":
        url = spec.url or settings.target_url
        if not url:
            raise TargetError(
                "the scenario targets an external URL but none is configured; "
                "pass --url or set BUGSAFARI_TARGET_URL"
            )
        yield ResolvedTarget(url=url)
        return

    if app_factory is None:
        raise TargetError(
            "the 'local_demo' target requires an application factory; "
            "pass one from the entry point"
        )
    with managed_server(app_factory, settings.demo_host) as url:
        yield ResolvedTarget(url=url, managed=True)


@contextmanager
def managed_server(
    app_factory: AppFactory,
    host: str = "127.0.0.1",
    ready_timeout_s: float = READY_TIMEOUT_S,
) -> Iterator[str]:
    """Run a WSGI app on an ephemeral port and always shut it down."""
    server = make_server(host, 0, app_factory())
    url = f"http://{host}:{server.server_port}"
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        _wait_until_ready(url, ready_timeout_s)
    except Exception:
        _stop(server, thread)
        raise
    try:
        yield url
    finally:
        _stop(server, thread)


def _wait_until_ready(url: str, timeout_s: float) -> None:
    deadline = monotonic() + timeout_s
    while monotonic() < deadline:
        try:
            with urlopen(url, timeout=0.25):
                return
        except Exception:  # noqa: BLE001 - any failure just means "not ready yet"
            sleep(READY_POLL_S)
    raise TargetError(f"local server at {url} did not become ready within {timeout_s}s")


def _stop(server: object, thread: Thread) -> None:
    shutdown = getattr(server, "shutdown", None)
    if callable(shutdown):
        shutdown()
    thread.join(timeout=3)
