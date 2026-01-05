from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlmodel import Session, select
import secrets
import string

from db import create_db_and_tables, get_session
from models import Event, Participant


app = FastAPI()
@app.get("/", response_class=HTMLResponse)
def read_root():
    return "<h1>Welcome to the Speed Friending application!</h1>"

class EventCreate(BaseModel):
    title: str
class JoinRequest(BaseModel):
    email: str


def generate_join_code(n: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))

@app.post("/events")
def create_event(payload: EventCreate, session: Session = Depends(get_session)):
    join_code = generate_join_code()
    while session.exec(select(Event).where(Event.join_code == join_code)).first():
        join_code = generate_join_code()

    event = Event(title=payload.title, join_code=join_code)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event
@app.on_event("startup")
def on_startup():
    import models  # гарантируем регистрацию таблиц
    create_db_and_tables()

@app.post("/events/{join_code}/join")
def join_event(join_code: str, payload: JoinRequest, session: Session = Depends(get_session)):
    event = session.exec(select(Event).where(Event.join_code == join_code)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    existing = session.exec(
        select(Participant).where(
            Participant.event_id == event.id,
            Participant.email == payload.email,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Participant with this email already joined the event")
    
    participant = Participant(event_id=event.id, email=payload.email)
    session.add(participant)
    session.commit()
    session.refresh(participant)
    return participant

@app.get("/events/{join_code}/participants")
def list_participants(join_code: str, session: Session = Depends(get_session)):
    event = session.exec(select(Event).where(Event.join_code == join_code)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    participants = session.exec(
        select(Participant).where(Participant.event_id == event.id)
    ).all()
    return {"event_id": event.id, "join_code": join_code, "participants": participants}