"""Lightweight Prometheus ``/metrics`` endpoint for the worker process.

The API process exposes ``/metrics`` through FastAPI. The worker is a
standalone process with no HTTP server, so it needs its own small endpoint
for Prometheus to scrape its ingestion metrics and worker-state gauge.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from prometheus_client import CONTENT_TYPE_LATEST, generate_latest


class _MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/metrics":
            body = generate_latest()
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args) -> None:
        # The worker already emits structured JSON logs; silence request logs.
        del format, args


def start_metrics_server(port: int = 9100) -> ThreadingHTTPServer:
    """Start a background HTTP server exposing ``/metrics`` (daemon thread).

    Returns the running server so callers can shut it down (e.g. in tests).
    """
    server = ThreadingHTTPServer(("0.0.0.0", port), _MetricsHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
