import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EventOut(BaseModel):
    """Individual event record with full details."""

    id: uuid.UUID = Field(
        ...,
        description="Unique identifier for the event",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
    )
    source: str = Field(
        ...,
        description="Data source identifier (e.g., 'aisstream')",
        json_schema_extra={"example": "aisstream"},
    )
    event_type: str = Field(
        ...,
        description="Type of event (e.g., 'PositionReport', 'VesselInfo')",
        json_schema_extra={"example": "PositionReport"},
    )
    payload: dict[str, Any] = Field(
        ...,
        description="Raw event data from source containing AIS message details",
        json_schema_extra={
            "example": {
                "MessageType": "PositionReport",
                "MetaData": {"MMSI": 123456789, "time_utc": "2024-01-01 12:00:00"},
                "Message": {"Latitude": 37.9, "Longitude": 23.7, "SOG": 15.2, "COG": 45.3},
            }
        },
    )
    received_at: datetime = Field(
        ...,
        description="Timestamp when event was received by the ingestion service",
        json_schema_extra={"example": "2024-01-01T12:00:00Z"},
    )
    dedup_key: str | None = Field(
        None,
        description="Deduplication key for idempotent processing (MMSI:event_type:timestamp)",
        json_schema_extra={"example": "mmsi:123456789:PositionReport:2024-01-01 12:00:00"},
    )

    model_config = {"from_attributes": True}


class EventQueryParams(BaseModel):
    """Parameters for filtering and querying events."""

    source: str | None = Field(
        None,
        description="Filter events by data source identifier",
        json_schema_extra={"example": "aisstream"},
    )
    event_type: str | None = Field(
        None,
        description="Filter events by AIS message type",
        json_schema_extra={"example": "PositionReport"},
    )
    start_time: datetime | None = Field(
        None,
        description="Filter events received after this ISO 8601 timestamp",
        json_schema_extra={"example": "2024-01-01T00:00:00Z"},
    )
    end_time: datetime | None = Field(
        None,
        description="Filter events received before this ISO 8601 timestamp",
        json_schema_extra={"example": "2024-01-01T23:59:59Z"},
    )
    cursor: str | None = Field(
        None,
        description="Base64 encoded pagination cursor from previous response",
        json_schema_extra={
            "example": (
                "MjAyNC0wMS0wMVQxMjowMDowMDo1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDA="
            )
        },
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of events to return per page (1-500)",
        json_schema_extra={"example": 50},
    )
    sort_order: str = Field(
        default="desc",
        pattern="^(asc|desc)$",
        description=(
            "Sort order by received timestamp ('asc' for oldest first, 'desc' for newest first)"
        ),
        json_schema_extra={"example": "desc"},
    )


class PaginatedEventsResponse(BaseModel):
    """Paginated response containing events and navigation metadata."""

    events: list[EventOut] = Field(
        ...,
        description="List of events matching the query parameters",
        min_length=0,
        max_length=500,
    )
    next_cursor: str | None = Field(
        None,
        description="Base64 encoded cursor for fetching the next page of results",
        json_schema_extra={
            "example": (
                "MjAyNC0wMS0wMVQxMjowMDowMDo1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDA="
            )
        },
    )
    has_more: bool = Field(
        ...,
        description="Indicates whether additional pages of results are available",
        json_schema_extra={"example": True},
    )
    total_count: int = Field(
        ...,
        description="Total number of events matching the query across all pages",
        ge=0,
        json_schema_extra={"example": 1500},
    )
