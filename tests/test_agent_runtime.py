
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from bugsafari.engine.agent_runtime import run_http_agents


class HealthyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"BugSafari test server is healthy")

    def log_message(self, format, *args):
        pass


def test_http_agents_run_through_coordinator():
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        HealthyHandler,
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        base_url = f"http://127.0.0.1:{server.server_port}"

        report = run_http_agents(
            base_url,
            count=5,
            max_concurrency=2,
        )

        assert report.requested_agents == 5
        assert report.completed_agents == 5
        assert report.failed_agents == 0
        assert report.verified_findings == []
        assert report.rejected_findings == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
