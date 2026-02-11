from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlmodel import Session, select
import secrets
import string

from db import create_db_and_tables, get_session
from models import Event, Participant, Round, Pairing, PairHistory


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

    # создаём БД и таблицы при старте
    create_db_and_tables()


@app.post("/events/{join_code}/join")
def join_event(
    join_code: str, payload: JoinRequest, session: Session = Depends(get_session)
):
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
        raise HTTPException(
            status_code=400,
            detail="Participant with this email already joined the event",
        )

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


from sqlmodel import select
from sqlalchemy import insert as sa_insert


def make_pairs(
    session: Session, event_id: int, participant_ids: list[int], round_number: int
):
    import random

    # все прошлые встречи в рамках события
    rows = session.exec(
        select(PairHistory.a_id, PairHistory.b_id).where(
            PairHistory.event_id == event_id
        )
    ).all()

    # нормализуем пары: (min,max), чтобы (2,5) == (5,2)
    met = {(min(a, b), max(a, b)) for (a, b) in rows}

    ids = participant_ids[:]
    random.shuffle(ids)

    pairs = []
    used = set()

    for p in ids:
        if p in used:
            continue

        partner = None
        for c in ids:
            if c == p or c in used:
                continue

            key = (min(p, c), max(p, c))
            if key not in met:
                partner = c
                break

        used.add(p)

        if partner is not None:
            used.add(partner)
            pairs.append((p, partner))

            a = min(p, partner)
            b = max(p, partner)

            # Try to insert pairhistory in a DB-safe way. For SQLite use INSERT OR IGNORE
            stmt = sa_insert(PairHistory.__table__).values(
                event_id=event_id, a_id=a, b_id=b, round_number=round_number
            )
            # SQLite supports OR IGNORE
            try:
                stmt = stmt.prefix_with("OR IGNORE")
            except Exception:
                pass

            session.exec(stmt)
            met.add((a, b))  # чтобы в рамках одного раунда тоже не повторить
        else:
            pairs.append((p, None))

    return pairs


from datetime import datetime
from zoneinfo import ZoneInfo

MINSK_TZ = ZoneInfo("Europe/Minsk")


@app.post("/events/{join_code}/start_round")
def start_round(join_code: str, session: Session = Depends(get_session)):
    event = session.exec(select(Event).where(Event.join_code == join_code)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    # start_round запускает ТОЛЬКО первый раунд
    current_round = int(event.current_round or 0)
    if current_round > 0:
        raise HTTPException(
            status_code=400, detail="Event already started. Use /next_round."
        )

    # берём участников события
    participants = session.exec(
        select(Participant).where(Participant.event_id == event.id)
    ).all()

    if len(participants) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 participants")

    # увеличиваем номер раунда
    next_round_num = current_round + 1
    event.current_round = next_round_num
    event.status = "running"

    started_at = datetime.now(MINSK_TZ)
    ends_at = started_at + timedelta(minutes=8)

    event.phase = "talk"
    event.phase_ends_at = ends_at

    round_obj = Round(
        event_id=event.id,
        number=next_round_num,
        started_at=started_at,
        ends_at=ends_at,
    )

    session.add(round_obj)

    # генерим пары
    ids = [p.id for p in participants if p.id is not None]
    pairs = make_pairs(
        session=session,
        event_id=event.id,
        participant_ids=ids,
        round_number=next_round_num,
    )

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
            Participant.event_id == event.id, Participant.email == email
        )
    ).first()
    if not participant:
        raise HTTPException(
            status_code=404, detail="Participant not found in this event"
        )

    current_round = int(event.current_round or 0)
    if current_round <= 0:
        return {"status": "waiting", "current_round": 0}

    # Находим pairing текущего раунда, где участвует participant
    pairing = session.exec(
        select(Pairing).where(
            Pairing.event_id == event.id,
            Pairing.round_number == current_round,
            (Pairing.p1_id == participant.id) | (Pairing.p2_id == participant.id),
        )
    ).first()

    if not pairing:
        # На случай, если раунд стартовал, но паринг для конкретного участника не записался
        return {"status": "no_pair", "current_round": current_round}

    # Определяем partner_id
    partner_id = pairing.p2_id if pairing.p1_id == participant.id else pairing.p1_id

    # Нечётное число участников: partner_id может быть None
    if partner_id is None:
        return {"status": "no_pair", "current_round": current_round}

    partner = session.exec(
        select(Participant).where(Participant.id == partner_id)
    ).first()
    if not partner:
        # Редкий кейс: в pairing есть id, но участника нет
        return {"status": "no_pair", "current_round": current_round}

    return {
        "status": "paired",
        "current_round": current_round,
        "partner": {
            "id": partner.id,
            "email": partner.email,
        },
    }


@app.get("/events/{join_code}/state")
def event_state(join_code: str, session: Session = Depends(get_session)):
    event = session.exec(select(Event).where(Event.join_code == join_code)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    participants_count = len(
        session.exec(select(Participant).where(Participant.event_id == event.id)).all()
    )

    current_round = int(event.current_round or 0)

    ends_at = getattr(event, "phase_ends_at", None)
    if ends_at is None and current_round > 0:
        round_row = session.exec(
            select(Round).where(
                Round.event_id == event.id, Round.number == current_round
            )
        ).first()
        if round_row:
            ends_at = round_row.ends_at

    now = datetime.now(MINSK_TZ)
    if ends_at is not None and getattr(ends_at, "tzinfo", None) is None:
        ends_at = ends_at.replace(tzinfo=MINSK_TZ)

    seconds_left = 0
    if ends_at:
        seconds_left = max(0, int((ends_at - now).total_seconds()))

    pairings_count = 0
    if current_round > 0:
        pairings_count = len(
            session.exec(
                select(Pairing).where(
                    Pairing.event_id == event.id,
                    Pairing.round_number == current_round,
                )
            ).all()
        )

    return {
        "join_code": event.join_code,
        "status": event.status,
        "current_round": current_round,
        "phase": getattr(event, "phase", "lobby"),
        "seconds_left": seconds_left,
        "participants_count": participants_count,
        "pairings_count": pairings_count,
    }


@app.get("/events/{join_code}/timer")
def event_timer(join_code: str, session: Session = Depends(get_session)):
    event = session.exec(select(Event).where(Event.join_code == join_code)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    current_round = int(event.current_round or 0)
    if current_round <= 0:
        return {"phase": "lobby", "seconds_left": None, "round": 0}

    round_obj = session.exec(
        select(Round).where(Round.event_id == event.id, Round.number == current_round)
    ).first()
    if not round_obj:
        return {"phase": "running", "seconds_left": None, "round": event.current_round}

    now = datetime.now(MINSK_TZ)
    ends_at = round_obj.ends_at
    if ends_at.tzinfo is None:
        ends_at = ends_at.replace(tzinfo=MINSK_TZ)

    seconds_left = int((ends_at - now).total_seconds())
    if seconds_left < 0:
        seconds_left = 0

    return {
        "phase": "running",
        "seconds_left": seconds_left,
        "round": event.current_round,
    }


@app.post("/events/{join_code}/next_round")
def next_round(join_code: str, session: Session = Depends(get_session)):
    event = session.exec(select(Event).where(Event.join_code == join_code)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if not event.current_round or event.current_round <= 0:
        raise HTTPException(
            status_code=400, detail="Event not started yet. Use /start_round."
        )

    participants = session.exec(
        select(Participant).where(Participant.event_id == event.id)
    ).all()
    if len(participants) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 participants")

    current_phase = getattr(event, "phase", "talk")

    # If currently in talk phase, transition to break (1 minute)
    if current_phase == "talk":
        now = datetime.now(MINSK_TZ)
        break_ends_at = now + timedelta(minutes=1)
        event.phase = "break"
        event.phase_ends_at = break_ends_at
        session.add(event)
        session.commit()
        return {
            "event_id": event.id,
            "round": event.current_round,
            "phase": "break",
            "started_at": now,
            "ends_at": break_ends_at,
            "message": "One-minute break started. No pairings created yet.",
        }

    # If in break or lobby phase, start next round (talk phase)
    new_round_number = int(event.current_round or 0) + 1

    started_at = datetime.now(MINSK_TZ)
    ends_at = started_at + timedelta(minutes=8)

    # создаём запись round
    session.add(
        Round(
            event_id=event.id,
            number=new_round_number,
            started_at=started_at,
            ends_at=ends_at,
        )
    )

    # генерим пары (учитывает PairHistory)
    ids = [p.id for p in participants if p.id is not None]
    pairs = make_pairs(
        session=session,
        event_id=event.id,
        participant_ids=ids,
        round_number=new_round_number,
    )

    # сохраняем пары
    for p1_id, p2_id in pairs:
        session.add(
            Pairing(
                event_id=event.id,
                round_number=new_round_number,
                p1_id=p1_id,
                p2_id=p2_id,
            )
        )

    # обновляем event
    event.current_round = new_round_number
    event.status = "running"
    event.phase = "talk"
    event.phase_ends_at = ends_at
    session.add(event)

    session.commit()

    return {
        "event_id": event.id,
        "round": new_round_number,
        "started_at": started_at,
        "ends_at": ends_at,
        "pairings_count": len(pairs),
    }
