import uuid
from datetime import datetime

from pydantic import BaseModel


class EventOut(BaseModel):
    id: uuid.UUID
    source: str
    event_type: str
    payload: dict
    received_at: datetime
    dedup_key: str | None

    model_config = {"from_attributes": True}
