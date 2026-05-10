import base64
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from feedstream.database import get_session
from feedstream.models import Event
from feedstream.schemas import EventQueryParams, PaginatedEventsResponse
from feedstream.redis_client import get_redis_client
from feedstream.rate_limiter import limiter, get_rate_limit

from feedstream.rate_limiter import limiter, rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

app = FastAPI(
    title="feedstream",
    description="Real-time AIS maritime data ingestion and query service with advanced filtering, pagination, and caching",
    version="0.3.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
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
    contact={
        "name": "feedstream API Support",
        "url": "https://github.com/Archangel-77/feedstream",
        "email": "support@example.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
)

# Add rate limiting middleware and exception handler
app.add_middleware(SlowAPIMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@app.get(
    "/healthz",
    tags=["ops"],
    summary="Health Check",
    description="Returns the current health status of the API service.",
    responses={
        200: {
            "description": "Service is healthy",
            "content": {
                "application/json": {
                    "example": {"status": "ok"}
                }
            }
        }
    }
)
@limiter.limit(get_rate_limit("ops"))
async def health(request: Request) -> dict:
    """Check if the API service is running and healthy."""
    return {"status": "ok"}


@app.get(
    "/events",
    response_model=PaginatedEventsResponse,
    tags=["events"],
    summary="List Events",
    description="Retrieve AIS maritime events with advanced filtering, sorting, and cursor-based pagination. "
    "Results are cached for 5 minutes to improve performance. Cache is automatically invalidated when new events are added.",
    responses={
        200: {
            "description": "List of events with pagination metadata",
            "content": {
                "application/json": {
                    "example": {
                        "events": [
                            {
                                "id": "550e8400-e29b-41d4-a716-446655440000",
                                "source": "aisstream",
                                "event_type": "PositionReport",
                                "payload": {
                                    "MessageType": "PositionReport",
                                    "MetaData": {"MMSI": 123456789},
                                    "Message": {"Latitude": 37.9, "Longitude": 23.7}
                                },
                                "received_at": "2024-01-01T12:00:00Z",
                                "dedup_key": "mmsi:123456789:PositionReport:2024-01-01 12:00:00"
                            }
                        ],
                        "next_cursor": "MjAyNC0wMS0wMVQxMjowMDowMDo1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDA=",
                        "has_more": True,
                        "total_count": 1500
                    }
                }
            }
        },
        400: {
            "description": "Invalid cursor format",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid cursor format"}
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Rate limit exceeded",
                        "error": "Too many requests. Limit: 100/minute",
                        "retry_after": "60"
                    }
                }
            }
        }
    }
)
@limiter.limit(get_rate_limit("events"))
async def list_events(
    request: Request,
    session: SessionDep,
    source: str | None = Query(
        None, 
        description="Filter events by data source (e.g., 'aisstream')",
        examples={"aisstream": {"value": "aisstream", "description": "AIS stream data source"}}
    ),
    event_type: str | None = Query(
        None, 
        description="Filter events by type (e.g., 'PositionReport', 'VesselInfo')",
        examples={"position": {"value": "PositionReport", "description": "Vessel position report"}}
    ),
    start_time: datetime | None = Query(
        None, 
        description="Filter events received after this timestamp (ISO 8601 format)",
        examples={"sample": {"value": "2024-01-01T00:00:00Z", "description": "Start of 2024"}}
    ),
    end_time: datetime | None = Query(
        None, 
        description="Filter events received before this timestamp (ISO 8601 format)",
        examples={"sample": {"value": "2024-01-01T23:59:59Z", "description": "End of 2024"}}
    ),
    cursor: str | None = Query(
        None, 
        description="Pagination cursor from previous response for navigating to next page",
        examples={"sample": {"value": "MjAyNC0wMS0wMVQxMjowMDowMDo1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDA=", "description": "Sample cursor for pagination"}}
    ),
    limit: int = Query(
        default=50, 
        ge=1, 
        le=500, 
        description="Maximum number of events to return per page (1-500)",
        examples={"default": {"value": 50, "description": "Default page size"}}
    ),
    sort_order: str = Query(
        default="desc", 
        pattern="^(asc|desc)$", 
        description="Sort order by received timestamp ('asc' for oldest first, 'desc' for newest first)",
        examples={"newest": {"value": "desc", "description": "Newest events first"}, "oldest": {"value": "asc", "description": "Oldest events first"}}
    ),
) -> PaginatedEventsResponse:
    """List events with filtering, sorting, and cursor-based pagination.
    
    Supports filtering by source, event type, and time ranges. Uses cursor-based pagination
    for efficient navigation through large datasets. The cursor is base64 encoded tuple of
    (received_at, id) for stable ordering. Results are cached for 5 minutes.
    """
    # Generate cache key
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
    
    # Try to get from cache first
    cached_result = await redis_client_instance.get(cache_key)
    if cached_result:
        return PaginatedEventsResponse(**cached_result)
    
    # Build base query with filters
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
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await session.execute(count_query)
    total_count = count_result.scalar()
    
    # Apply cursor-based pagination
    if cursor:
        try:
            decoded = base64.b64decode(cursor.encode()).decode()
            # Split on the last colon to handle datetime strings properly
            last_colon_index = decoded.rfind(":")
            if last_colon_index == -1:
                raise ValueError("Invalid cursor format")
            received_at_str = decoded[:last_colon_index]
            event_id_str = decoded[last_colon_index + 1:]
            cursor_received_at = datetime.fromisoformat(received_at_str)
            cursor_event_id = uuid.UUID(event_id_str)
            
            if sort_order == "desc":
                query = query.where(
                    or_(Event.received_at < cursor_received_at,
                        and_(Event.received_at == cursor_received_at, Event.id < cursor_event_id))
                )
            else:
                query = query.where(
                    or_(Event.received_at > cursor_received_at,
                        and_(Event.received_at == cursor_received_at, Event.id > cursor_event_id))
                )
        except (ValueError, IndexError) as e:
            raise HTTPException(status_code=400, detail="Invalid cursor format")
    
    # Apply sorting and limit
    if sort_order == "desc":
        query = query.order_by(Event.received_at.desc(), Event.id.desc())
    else:
        query = query.order_by(Event.received_at.asc(), Event.id.asc())
    
    query = query.limit(limit + 1)  # Fetch one extra to determine if more results exist
    
    # Execute query
    result = await session.execute(query)
    events = list(result.scalars().all())
    
    # Determine pagination metadata
    has_more = len(events) > limit
    if has_more:
        events = events[:-1]  # Remove the extra item
        
        # Generate next cursor from last event
        last_event = events[-1]
        next_cursor = base64.b64encode(
            f"{last_event.received_at.isoformat()}:{last_event.id}".encode()
        ).decode()
    else:
        next_cursor = None
    
    response = PaginatedEventsResponse(
        events=events,
        next_cursor=next_cursor,
        has_more=has_more,
        total_count=total_count,
    )
    
    # Cache the result for 5 minutes (300 seconds)
    await redis_client_instance.set(cache_key, response.model_dump(), ttl=300)
    
    return response
