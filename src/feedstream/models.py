import uuid
from datetime import datetime

from sqlalchemy import DateTime, JSON, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from feedstream.database import Base

# On Postgres: native JSONB. On SQLite (tests): plain JSON.
_payload_type = JSON().with_variant(JSONB, "postgresql")


class Event(Base):
    __tablename__ = "events"

    # sqlalchemy.Uuid handles UUID natively on Postgres and as TEXT on SQLite
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(_payload_type, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    dedup_key: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
