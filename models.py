from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field
from zoneinfo import ZoneInfo
from sqlalchemy import UniqueConstraint, Index, Column, DateTime
from sqlalchemy.types import TypeDecorator

MINSK_TZ = ZoneInfo("Europe/Minsk")

class UTCDateTime(TypeDecorator):
    """В БД хранит naive UTC, наружу отдаёт aware UTC. От TimeZone сессии не зависит."""
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        return None if value is None else value.replace(tzinfo=timezone.utc)

class Event(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    join_code: str = Field(index=True, unique=True)
    facilitator_pin: str = Field(default="")
    timezone: str = Field(default="Europe/Minsk")
    created_at: datetime = Field(default_factory=lambda: datetime.now(MINSK_TZ), sa_column=Column(UTCDateTime, nullable=False),)
    status: str = Field(default="created")
    current_round: int = Field(default=0)
    phase: str = Field(default="lobby")
    phase_ends_at: Optional[datetime] = Field(default=None, sa_column=Column(UTCDateTime))


class Participant(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: int = Field(index=True, foreign_key="event.id")
    nickname: str = Field(index=True)
    email: Optional[str] = Field(default=None)
    photo_filename: Optional[str] = Field(default=None)
    photo_uploaded_at: Optional[datetime] = Field(default=None, sa_column=Column(UTCDateTime))
    joined_at: datetime = Field(
        default_factory=lambda: datetime.now(MINSK_TZ),
        sa_column=Column(UTCDateTime, nullable=False),
    )


class Round(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: int = Field(index=True, foreign_key="event.id")
    number: int = Field(index=True)
    started_at: datetime = Field(sa_column=Column(UTCDateTime, nullable=False))
    ends_at: datetime = Field(sa_column=Column(UTCDateTime, nullable=False))


class Pairing(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: int = Field(index=True, foreign_key="event.id")
    round_number: int = Field(index=True)
    p1_id: int = Field(foreign_key="participant.id")
    p2_id: Optional[int] = Field(default=None, foreign_key="participant.id")
    status: str = Field(default="assigned")
    met_at: Optional[datetime] = Field(default=None, sa_column=Column(UTCDateTime))


class PairHistory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: int = Field(foreign_key="event.id", index=True)
    a_id: int = Field(foreign_key="participant.id")
    b_id: int = Field(foreign_key="participant.id")
    round_number: int = Field(index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(MINSK_TZ),
        sa_column=Column(UTCDateTime, nullable=False),
    )

    __table_args__ = (
        UniqueConstraint("event_id", "a_id", "b_id", name="uq_pairhistory_event_a_b"),
        Index("ix_pairhistory_event_a", "event_id", "a_id"),
    )


class Question(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: int = Field(index=True, foreign_key="event.id")
    round_number: int = Field(index=True)
    text: str = Field(max_length=500)
    created_at: datetime = Field(default_factory=lambda: datetime.now(MINSK_TZ))
