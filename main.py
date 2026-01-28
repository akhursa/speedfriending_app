from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlmodel import Session, select
import secrets
import string

from db import create_db_and_tables, get_session
from models import Event, Participant, Round, Pairing

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

from datetime import timedelta

def make_pairs(participant_ids: list[int]) -> list[tuple[int, int | None]]:
    """
    Возвращает список пар (p1_id, p2_id). Если нечётное — одна пара будет (id, None) = ожидание.
    """
    ids = participant_ids[:]
    # простое перемешивание
    import random
    random.shuffle(ids)

    pairs = []
    if len(ids) % 2 == 1:
        pairs.append((ids.pop(), None))  # один в ожидание

    for i in range(0, len(ids), 2):
        pairs.append((ids[i], ids[i + 1]))
    return pairs

from datetime import datetime
from zoneinfo import ZoneInfo

MINSK_TZ = ZoneInfo("Europe/Minsk")

@app.post("/events/{join_code}/start_round")
def start_round(join_code: str, session: Session = Depends(get_session)):
    event = session.exec(select(Event).where(Event.join_code == join_code)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # берём участников события
    participants = session.exec(
        select(Participant).where(Participant.event_id == event.id)
    ).all()

    if len(participants) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 participants")

    # увеличиваем номер раунда
    next_round_num = event.current_round + 1
    event.current_round = next_round_num
    event.status = "running"

    started_at = datetime.now(MINSK_TZ)
    ends_at = started_at + timedelta(minutes=8)

    round_obj = Round(
        event_id=event.id,
        number=next_round_num,
        started_at=started_at,
        ends_at=ends_at,
    )

    session.add(round_obj)

    # генерим пары
    ids = [p.id for p in participants if p.id is not None]
    pairs = make_pairs(ids)

    created_pairings = []
    for p1_id, p2_id in pairs:
        pairing = Pairing(
            event_id=event.id,
            round_number=next_round_num,
            p1_id=p1_id,
            p2_id=p2_id,
        )
        session.add(pairing)
        created_pairings.append(pairing)

    session.add(event)
    session.commit()

    return {
        "event_id": event.id,
        "round": next_round_num,
        "started_at": started_at,
        "ends_at": ends_at,
        "pairings_count": len(created_pairings),
    }
@app.get("/events/{join_code}/my_match")
def my_match(join_code: str, email: str, session: Session = Depends(get_session)):
    event = session.exec(select(Event).where(Event.join_code == join_code)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    participant = session.exec(
        select(Participant).where(
            Participant.event_id == event.id,
            Participant.email == email,
        )
    ).first()
    if not participant or participant.id is None:
        raise HTTPException(status_code=404, detail="Participant not found")

    if event.current_round <= 0:
        raise HTTPException(status_code=400, detail="Round not started")

    pairing = session.exec(
        select(Pairing).where(
            Pairing.event_id == event.id,
            Pairing.round_number == event.current_round,
            ((Pairing.p1_id == participant.id) | (Pairing.p2_id == participant.id)),
        )
    ).first()

    if not pairing:
        raise HTTPException(status_code=404, detail="No pairing for current round")

    partner_id = pairing.p2_id if pairing.p1_id == participant.id else pairing.p1_id

    partner = None
    if partner_id is not None:
        partner = session.get(Participant, partner_id)

    round_obj = session.exec(
        select(Round).where(Round.event_id == event.id, Round.number == event.current_round)
    ).first()

    return {
        "event_id": event.id,
        "round": event.current_round,
        "me": {"id": participant.id, "email": participant.email},
        "partner": None if not partner else {"id": partner.id, "email": partner.email},
        "started_at": None if not round_obj else round_obj.started_at,
        "ends_at": None if not round_obj else round_obj.ends_at,
        "pairing": {"id": pairing.id, "status": pairing.status},
    }
