from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field
from zoneinfo import ZoneInfo

Minsk_tz = ZoneInfo("Europe/Minsk")

class Event(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    join_code: str = Field(index=True, unique=True)
    timezone: str =  Field(default="Europe/Minsk")
    created_at: datetime = Field(default_factory=lambda: datetime.now(Minsk_tz))

class Participant(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: int = Field(index=True, foreign_key="event.id")
    email: str = Field(index=True)
    joined_at: datetime = Field(default_factory=lambda: datetime.now(Minsk_tz))

from datetime import timedelta

class Round(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: int = Field(index=True, foreign_key="event.id")
    number: int = Field(index=True)  # 1,2,3...
    started_at: datetime
    ends_at: datetime

class Pairing(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: int = Field(index=True, foreign_key="event.id")
    round_number: int = Field(index=True)
    p1_id: int = Field(foreign_key="participant.id")
    p2_id: Optional[int] = Field(default=None, foreign_key="participant.id")  # None = ожидание
    status: str = Field(default="assigned")  # assigned/met/missed
    met_at: Optional[datetime] = Field(default=None)
