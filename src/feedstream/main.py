from typing import Annotated

from fastapi import Depends, FastAPI, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from feedstream.database import get_session
from feedstream.models import Event
from feedstream.schemas import EventOut

app = FastAPI(
    title="feedstream",
    description="Real-time AIS maritime data ingestion and query service",
    version="0.1.0",
)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@app.get("/healthz", tags=["ops"])
async def health() -> dict:
    return {"status": "ok"}


@app.get("/events", response_model=list[EventOut], tags=["events"])
async def list_events(
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=500),
) -> list[Event]:
    result = await session.execute(
        select(Event).order_by(Event.received_at.desc()).limit(limit)
    )
    return list(result.scalars().all())
