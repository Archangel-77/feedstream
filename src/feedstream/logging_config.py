"""Structured JSON logging shared by the API, worker, and retention processes.

Every process in the service routes its logs through the ``feedstream`` package
logger so output is consistently JSON with a ``correlation_id`` field that ties
together the request (API) or ingestion trace (worker).
"""

import logging

from pythonjsonlogger import jsonlogger

from feedstream.observability.tracing import get_correlation_id


class CorrelationIdFilter(logging.Filter):
    """Inject the current correlation ID into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id() or "-"
        return True


def configure_logging(level: str = "INFO") -> None:
    """Attach a JSON formatter to the ``feedstream`` package logger.

    Idempotent: re-running does not stack duplicate handlers (safe under
    uvicorn reload and repeated test imports).
    """
    package_logger = logging.getLogger("feedstream")
    if any(
        isinstance(handler.formatter, jsonlogger.JsonFormatter)
        for handler in package_logger.handlers
    ):
        return

    handler = logging.StreamHandler()
    handler.addFilter(CorrelationIdFilter())
    handler.setFormatter(jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    package_logger.addHandler(handler)
    package_logger.setLevel(level.upper())
    package_logger.propagate = False
