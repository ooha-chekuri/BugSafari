
"""Local-only HTTP probe worker for BugSafari."""
from __future__ import annotations

from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from bugsafari.engine.multi_agent import (
    AgentResult,
    AgentTask,
    FindingReport,
)


def _validate_local_base_url(base_url: str) -> str:
    """Allow only local HTTP or HTTPS targets."""
    parsed = urlparse(base_url)

    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Target URL must use http:// or https://")

    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError(
            "This initial HTTP worker only allows localhost or loopback IPs"
        )

    if parsed.username or parsed.password:
        raise ValueError("Do not embed credentials in the target URL")

    return base_url.rstrip("/") + "/"


class HTTPProbeWorker:
    """Check local endpoints using GET requests."""

    def __init__(
        self,
        base_url: str,
        paths: tuple[str, ...] = ("/",),
        timeout_seconds: float = 3.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not paths:
            raise ValueError("At least one path is required")

        self.base_url = _validate_local_base_url(base_url)
        self.paths = paths
        self.timeout_seconds = timeout_seconds

    def __call__(self, task: AgentTask) -> AgentResult:
        if task.mode != "http":
            return AgentResult(
                agent_id=task.agent_id,
                status="completed",
            )

        findings: list[FindingReport] = []

        for path in self.paths:
            if (
                not path.startswith("/")
                or path.startswith("//")
                or "://" in path
            ):
                return AgentResult(
                    agent_id=task.agent_id,
                    status="failed",
                    error=f"Only absolute local paths are allowed: {path!r}",
                )

            url = urljoin(self.base_url, path.lstrip("/"))
            started = perf_counter()

            try:
                request = Request(
                    url,
                    method="GET",
                    headers={
                        "User-Agent": "BugSafari-Local-HTTP-Probe/1.0"
                    },
                )

                with urlopen(
                    request,
                    timeout=self.timeout_seconds,
                ) as response:
                    status_code = response.status
                    response.read(1024)

            except HTTPError as exc:
                status_code = exc.code
                exc.close()

            except (URLError, TimeoutError, OSError) as exc:
                elapsed_ms = round(
                    (perf_counter() - started) * 1000, 2
                )
                findings.append(
                    FindingReport(
                        title="Local endpoint request failed",
                        target=url,
                        rule="http_request_completes",
                        expected="A valid HTTP response",
                        actual=f"{type(exc).__name__}: {exc}",
                        reproduction_steps=(f"Send GET {url}",),
                        evidence=(f"Elapsed time: {elapsed_ms} ms",),
                        suggested_fix=(
                            "Check the local server and endpoint."
                        ),
                    )
                )
                continue

            elapsed_ms = round(
                (perf_counter() - started) * 1000, 2
            )

            if status_code >= 500:
                findings.append(
                    FindingReport(
                        title="Server returned an HTTP 5xx response",
                        target=url,
                        rule="http_status_below_500",
                        expected="HTTP status below 500",
                        actual=f"HTTP {status_code}",
                        reproduction_steps=(f"Send GET {url}",),
                        evidence=(
                            f"HTTP status: {status_code}",
                            f"Elapsed time: {elapsed_ms} ms",
                        ),
                        suggested_fix=(
                            "Inspect server logs and exception handling."
                        ),
                    )
                )

        return AgentResult(
            agent_id=task.agent_id,
            status="completed",
            findings=tuple(findings),
        )
