import urllib.error
import urllib.request

import pytest

from feedstream.observability.metrics import METRIC_EVENTS_INGESTED_TOTAL
from feedstream.worker_metrics import start_metrics_server


def test_metrics_server_exposes_worker_metrics():
    server = start_metrics_server(port=0)
    port = server.server_address[1]
    try:
        METRIC_EVENTS_INGESTED_TOTAL.labels(
            source="test", event_type="test", status="inserted"
        ).inc()

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=5) as resp:
            body = resp.read().decode()

        assert resp.status == 200
        assert "feedstream_events_ingested_total" in body
        assert 'status="inserted"' in body
    finally:
        server.shutdown()
        server.server_close()


def test_metrics_server_404_on_unknown_path():
    server = start_metrics_server(port=0)
    port = server.server_address[1]
    try:
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(f"http://127.0.0.1:{port}/nope", timeout=5)
    finally:
        server.shutdown()
        server.server_close()
