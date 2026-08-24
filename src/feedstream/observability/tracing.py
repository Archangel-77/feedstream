from contextvars import ContextVar
from uuid import uuid4

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
ingestion_trace_id_ctx: ContextVar[str | None] = ContextVar("ingestion_trace_id", default=None)


def new_trace_id() -> str:
    return str(uuid4())


def set_request_id(request_id: str) -> None:
    request_id_ctx.set(request_id)


def get_request_id() -> str | None:
    return request_id_ctx.get()


def get_correlation_id() -> str | None:
    """Return the active correlation ID (request ID, or ingestion trace ID)."""
    return request_id_ctx.get() or ingestion_trace_id_ctx.get()


def set_ingestion_trace_id(trace_id: str) -> None:
    ingestion_trace_id_ctx.set(trace_id)


def get_ingestion_trace_id() -> str | None:
    return ingestion_trace_id_ctx.get()
