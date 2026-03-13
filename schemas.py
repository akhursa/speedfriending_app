from pydantic import BaseModel
from typing import Optional


class EventCreate(BaseModel):
    title: str


class EventResponse(BaseModel):
    id: int
    title: str
    join_code: str
    facilitator_pin: str
    created_at: str
    status: str


class JoinRequest(BaseModel):
    nickname: str
    email: Optional[str] = None


class QuestionsUploadRequest(BaseModel):
    questions: list[str]


class MarkMetRequest(BaseModel):
    nickname: str
