import base64
import logging
import time
import uuid
from datetime import datetime
from typing import Annotated, cast

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from feedstream.database import get_pool_stats, get_session
from feedstream.logging_config import configure_logging
from feedstream.models import Event
from feedstream.observability.metrics import (
    METRIC_HTTP_REQUESTS_TOTAL,
    get_metrics_payload,
    metrics_snapshot,
    observe_db_pool,
    observe_query_latency,
)
from feedstream.observability.tracing import new_trace_id, set_request_id
from feedstream.rate_limiter import get_rate_limit, limiter, rate_limit_exceeded_handler
from feedstream.redis_client import get_redis_client
from feedstream.schemas import EventOut, PaginatedEventsResponse
from feedstream.settings import settings

logger = logging.getLogger(__name__)

configure_logging(settings.log_level)


def build_openapi_config() -> dict:
    """Return the docs-related FastAPI options, honoring ENABLE_DOCS."""
    return {
        "docs_url": "/docs" if settings.enable_docs else None,
        "redoc_url": "/redoc" if settings.enable_docs else None,
        "openapi_url": "/openapi.json" if settings.enable_docs else None,
    }


app = FastAPI(
    title="feedstream",
    description=(
        "Real-time AIS maritime data ingestion and query service "
        "with advanced filtering, pagination, and caching"
    ),
    version="0.4.0",
    **build_openapi_config(),
    servers=[{"url": settings.public_base_url}],
    openapi_tags=[
        {
            "name": "ops",
            "description": "Operational endpoints for monitoring and health checks",
        },
        {
            "name": "events",
            "description": "Event querying and filtering endpoints with pagination support",
        },
    ],
)

app.add_middleware(SlowAPIMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@app.middleware("http")
async def tracing_and_metrics_middleware(request: Request, call_next):
    started_at = time.perf_counter()
    request_id = request.headers.get("X-Request-ID") or new_trace_id()
    set_request_id(request_id)
    request.state.request_id = request_id

    response = await call_next(request)

    elapsed = time.perf_counter() - started_at
    METRIC_HTTP_REQUESTS_TOTAL.labels(
        method=request.method,
        path=request.url.path,
        status_code=str(response.status_code),
    ).inc()
    logger.info(
        "request_completed",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": str(response.status_code),
            "response_time_ms": f"{elapsed * 1000:.2f}",
        },
    )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time"] = f"{elapsed:.6f}"
    return response


@app.get("/healthz", tags=["ops"])
@limiter.limit(get_rate_limit("ops"))
async def health(request: Request) -> dict:
    return {"status": "ok"}


@app.get("/", tags=["ops"], response_class=HTMLResponse)
async def landing() -> str:
    metrics_link = (
        '<li><a href="/metrics"><code>/metrics</code> - Prometheus metrics</a></li>'
        if settings.enable_metrics
        else ""
    )
    docs_link = (
        '<li><a href="/docs"><code>/docs</code> - Interactive API docs</a></li>'
        if settings.enable_docs
        else ""
    )
    return f"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>feedstream</title>
    <style>
      body {{
        font-family: -apple-system, Segoe UI, sans-serif;
        margin: 2rem auto;
        max-width: 760px;
        padding: 0 1rem;
        line-height: 1.5;
        color: #1f2937;
      }}
      h1 {{ margin-bottom: 0.25rem; }}
      .muted {{ color: #4b5563; }}
      code {{ background: #f3f4f6; padding: 0.1rem 0.25rem; border-radius: 4px; }}
      a {{ color: #0f766e; text-decoration: none; }}
      a:hover {{ text-decoration: underline; }}
    </style>
  </head>
  <body>
    <h1>feedstream</h1>
    <p class="muted">Real-time AIS ingestion and query API.</p>
    <ul>
      <li><a href="/healthz"><code>/healthz</code> - Health check</a></li>
      {docs_link}
      {metrics_link}
      <li><a href="{settings.github_repo_url}">GitHub repository</a></li>
    </ul>
  </body>
</html>
"""


@app.get("/metrics", tags=["ops"])
async def metrics() -> Response:
    if not settings.enable_metrics:
        raise HTTPException(status_code=404, detail="Metrics disabled")
    payload, content_type = get_metrics_payload()
    return Response(content=payload, media_type=content_type)


@app.get("/debug/stats", tags=["ops"])
async def debug_stats(x_debug_token: str = Header(default="")) -> dict:
    if not settings.debug_stats_token or x_debug_token != settings.debug_stats_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    pool_stats = get_pool_stats()
    observe_db_pool(pool_stats)
    redis_client = await get_redis_client()
    snapshot = metrics_snapshot(pool_stats, redis_client.get_cache_stats())
    snapshot["timestamp"] = datetime.utcnow().isoformat()
    return snapshot


@app.get(
    "/events",
    response_model=PaginatedEventsResponse,
    tags=["events"],
)
@limiter.limit(get_rate_limit("events"))
async def list_events(
    request: Request,
    session: SessionDep,
    source: Annotated[str | None, Query()] = None,
    event_type: Annotated[str | None, Query()] = None,
    start_time: Annotated[datetime | None, Query()] = None,
    end_time: Annotated[datetime | None, Query()] = None,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    sort_order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
) -> PaginatedEventsResponse:
    started_at = time.perf_counter()

    redis_client_instance = await get_redis_client()
    cache_key = redis_client_instance.generate_cache_key(
        "events",
        source=source,
        event_type=event_type,
        start_time=start_time.isoformat() if start_time else None,
        end_time=end_time.isoformat() if end_time else None,
        cursor=cursor,
        limit=limit,
        sort_order=sort_order,
    )

    cached_result = await redis_client_instance.get(cache_key)
    if cached_result:
        observe_query_latency("/events", started_at)
        return PaginatedEventsResponse(**cached_result)

    query = select(Event)
    conditions = []

    if source:
        conditions.append(Event.source == source)
    if event_type:
        conditions.append(Event.event_type == event_type)
    if start_time:
        conditions.append(Event.received_at >= start_time)
    if end_time:
        conditions.append(Event.received_at <= end_time)

    if conditions:
        query = query.where(and_(*conditions))

    count_query = select(func.count()).select_from(query.subquery())
    count_result = await session.execute(count_query)
    total_count = int(count_result.scalar() or 0)

    if cursor:
        try:
            decoded = base64.b64decode(cursor.encode()).decode()
            last_colon_index = decoded.rfind(":")
            if last_colon_index == -1:
                raise ValueError("Invalid cursor format")
            received_at_str = decoded[:last_colon_index]
            event_id_str = decoded[last_colon_index + 1 :]
            cursor_received_at = datetime.fromisoformat(received_at_str)
            cursor_event_id = uuid.UUID(event_id_str)

            if sort_order == "desc":
                query = query.where(
                    or_(
                        Event.received_at < cursor_received_at,
                        and_(Event.received_at == cursor_received_at, Event.id < cursor_event_id),
                    )
                )
            else:
                query = query.where(
                    or_(
                        Event.received_at > cursor_received_at,
                        and_(Event.received_at == cursor_received_at, Event.id > cursor_event_id),
                    )
                )
        except (ValueError, IndexError):
            raise HTTPException(status_code=400, detail="Invalid cursor format") from None

    if sort_order == "desc":
        query = query.order_by(Event.received_at.desc(), Event.id.desc())
    else:
        query = query.order_by(Event.received_at.asc(), Event.id.asc())

    query = query.limit(limit + 1)

    result = await session.execute(query)
    events = list(result.scalars().all())

    has_more = len(events) > limit
    if has_more:
        events = events[:-1]
        last_event = events[-1]
        next_cursor = base64.b64encode(
            f"{last_event.received_at.isoformat()}:{last_event.id}".encode()
        ).decode()
    else:
        next_cursor = None

    response = PaginatedEventsResponse(
        events=cast(list[EventOut], events),
        next_cursor=next_cursor,
        has_more=has_more,
        total_count=total_count,
    )

    await redis_client_instance.set(cache_key, response.model_dump(), ttl=300)
    observe_query_latency("/events", started_at)

    return response
