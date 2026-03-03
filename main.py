from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from typing import Optional
from sqlmodel import Session, select
import secrets
import string
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from dotenv import load_dotenv

load_dotenv()

from config import config
from db import create_db_and_tables, get_session
from models import Event, Participant, Round, Pairing, PairHistory, Question
from validators import validate_nickname, validate_join_code, validate_event_title, validate_questions_batch


app = FastAPI(
    title="Speed Friending API",
    description="Real-time speed dating event management platform",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_HOSTS if config.is_production() else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Add trusted host middleware (security)
if config.is_production():
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=config.ALLOWED_HOSTS,
    )

# Set up Jinja2 template environment
templates_dir = Path(__file__).parent / "templates"
jinja_env = Environment(loader=FileSystemLoader(str(templates_dir)))


@app.get("/", response_class=HTMLResponse)
def read_root():
    template = jinja_env.get_template("index.html")
    return template.render()

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

def generate_join_code(n: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def generate_facilitator_pin(n: int = 4) -> str:
    """Generate a 4-digit numeric PIN for facilitator authentication"""
    return "".join(secrets.choice(string.digits) for _ in range(n))


@app.post("/events", response_model=EventResponse)
def create_event(payload: EventCreate, session: Session = Depends(get_session)):
    # Validate event title
    is_valid, error_msg = validate_event_title(payload.title)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    join_code = generate_join_code()
    while session.exec(select(Event).where(Event.join_code == join_code)).first():
        join_code = generate_join_code()

    facilitator_pin = generate_facilitator_pin()
    
    event = Event(
        title=payload.title.strip(),
        join_code=join_code,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    
    # Return the event with a generated PIN (PIN is just generated on client side, not stored)
    return EventResponse(
        id=event.id,
        title=event.title,
        join_code=event.join_code,
        facilitator_pin=facilitator_pin,
        created_at=event.created_at.isoformat(),
        status=event.status,
    )


@app.get("/join", response_class=HTMLResponse)
def join_page(code: str = None):
    """
    Join event page where participants can enter their nickname and join code.
    The code can be provided as a query parameter for direct joining.
    """
    template = jinja_env.get_template("join.html")
    return template.render()


@app.get("/facilitator/login", response_class=HTMLResponse)
def facilitator_login():
    """
    Facilitator login page for authentication.
    """
    template = jinja_env.get_template("facilitator_login.html")
    return template.render()


@app.post("/events/{join_code}/verify_facilitator")
def verify_facilitator(join_code: str, pin: str, session: Session = Depends(get_session)):
    """
    Verify facilitator access (client-side validation only).
    This endpoint just verifies that the event exists.
    Actual PIN validation happens client-side via sessionStorage.
    """
    event = session.exec(select(Event).where(Event.join_code == join_code)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    return {"status": "authenticated", "join_code": join_code}


@app.get("/events/{join_code}/info")
def event_info(join_code: str, session: Session = Depends(get_session)):
    """
    Get event information/metadata.
    Returns: title, join_code, status, participant_count, total_pairings, etc.
    """
    event = session.exec(select(Event).where(Event.join_code == join_code)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Get participant count
    participant_count = len(
        session.exec(select(Participant).where(Participant.event_id == event.id)).all()
    )
    
    # Get total pairings across all rounds
    total_pairings = len(
        session.exec(select(Pairing).where(Pairing.event_id == event.id)).all()
    )
    
    # Get total unique pairs
    total_unique_pairs = len(
        session.exec(select(PairHistory).where(PairHistory.event_id == event.id)).all()
    )
    
    return {
        "id": event.id,
        "title": event.title,
        "join_code": event.join_code,
        "status": event.status,
        "created_at": event.created_at,
        "current_round": event.current_round,
        "phase": event.phase,
        "phase_ends_at": event.phase_ends_at,
        "timezone": event.timezone,
        "participant_count": participant_count,
        "total_pairings": total_pairings,
        "total_unique_pairs": total_unique_pairs,
    }


@app.on_event("startup")
def on_startup():
    import models  # гарантируем регистрацию таблиц

    # создаём БД и таблицы при старте
    create_db_and_tables()


@app.post("/events/{join_code}/join")
def join_event(
    join_code: str, payload: JoinRequest, session: Session = Depends(get_session)
):
    # Validate inputs
    code_valid, code_error = validate_join_code(join_code)
    if not code_valid:
        raise HTTPException(status_code=400, detail=code_error)
    
    nickname_valid, nickname_error = validate_nickname(payload.nickname)
    if not nickname_valid:
        raise HTTPException(status_code=400, detail=nickname_error)
    
    # Normalize nickname to lowercase
    normalized_nickname = payload.nickname.strip().lower()
    
    event = session.exec(select(Event).where(Event.join_code == join_code)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    existing = session.exec(
        select(Participant).where(
            Participant.event_id == event.id,
            Participant.nickname == normalized_nickname,
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Participant with this nickname already joined the event",
        )

    participant = Participant(
        event_id=event.id,
        nickname=normalized_nickname,
        email=payload.email
    )
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


from datetime import datetime, timedelta

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

    # If odd number of participants, pick who should rest this round
    # (the one who has rested the least so far, for fair rotation)
    rest_person = None
    if len(ids) % 2 == 1:
        rest_counts = {}
        for pid in participant_ids:
            # Count how many times this participant has rested (appeared with p2_id=None)
            rest_count = len(
                session.exec(
                    select(Pairing).where(
                        Pairing.event_id == event_id,
                        Pairing.p1_id == pid,
                        Pairing.p2_id == None,
                    )
                ).all()
            )
            rest_counts[pid] = rest_count

        # Pick the participant with the least rests.
        # For ties, rotate fairly using round_number and sorted order (by pid).
        min_rest = min(rest_counts.values())
        candidates = sorted([pid for pid in participant_ids if rest_counts[pid] == min_rest])
        # Use round_number to deterministically rotate among tied candidates
        rest_person = candidates[(round_number - 1) % len(candidates)]

    for p in ids:
        if p in used:
            continue

        # If this is the designated rest person, rest this round
        if p == rest_person:
            pairs.append((p, None))
            used.add(p)
            continue

        partner = None
        for c in ids:
            if c == p or c in used or c == rest_person:
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
            # This should not happen if rest_person is correctly identified
            pairs.append((p, None))

    # Flush to ensure PairHistory inserts are persisted
    session.flush()
    return pairs


from zoneinfo import ZoneInfo

MINSK_TZ = ZoneInfo("Europe/Minsk")

# Break duration configuration (loaded from config module which reads .env)
BREAK_DURATION_SECONDS = config.BREAK_DURATION_SECONDS


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
def my_match(join_code: str, nickname: str, session: Session = Depends(get_session)):
    event = session.exec(select(Event).where(Event.join_code == join_code)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Normalize nickname
    normalized_nickname = nickname.strip().lower()
    
    participant = session.exec(
        select(Participant).where(
            Participant.event_id == event.id, Participant.nickname == normalized_nickname
        )
    ).first()
    if not participant:
        raise HTTPException(
            status_code=404, detail="Participant not found in this event"
        )

    current_round = int(event.current_round or 0)
    if current_round <= 0:
        return {"status": "waiting", "current_round": 0}

    current_phase = getattr(event, "phase", "talk")

    # During TALK phase: show current round partner
    if current_phase == "talk":
        pairing = session.exec(
            select(Pairing).where(
                Pairing.event_id == event.id,
                Pairing.round_number == current_round,
                (Pairing.p1_id == participant.id) | (Pairing.p2_id == participant.id),
            )
        ).first()

        if not pairing:
            return {"status": "no_pair", "current_round": current_round, "phase": "talk"}

        partner_id = pairing.p2_id if pairing.p1_id == participant.id else pairing.p1_id

        if partner_id is None:
            return {"status": "no_pair", "current_round": current_round, "phase": "talk"}

        partner = session.exec(
            select(Participant).where(Participant.id == partner_id)
        ).first()
        if not partner:
            return {"status": "no_pair", "current_round": current_round, "phase": "talk"}

        return {
            "status": "paired",
            "phase": "talk",
            "current_round": current_round,
            "partner": {
                "id": partner.id,
                "nickname": partner.nickname,
            },
        }
    
    # During BREAK phase: show next round partner
    elif current_phase == "break":
        next_round = current_round + 1
        next_pairing = session.exec(
            select(Pairing).where(
                Pairing.event_id == event.id,
                Pairing.round_number == next_round,
                (Pairing.p1_id == participant.id) | (Pairing.p2_id == participant.id),
            )
        ).first()

        if not next_pairing:
            # Next round pairings not yet generated
            return {"status": "waiting_for_pairing", "phase": "break", "current_round": current_round}

        partner_id = next_pairing.p2_id if next_pairing.p1_id == participant.id else next_pairing.p1_id

        if partner_id is None:
            # This participant will rest in next round
            return {"status": "resting", "phase": "break", "current_round": current_round, "next_round": next_round}

        partner = session.exec(
            select(Participant).where(Participant.id == partner_id)
        ).first()
        if not partner:
            return {"status": "waiting_for_pairing", "phase": "break", "current_round": current_round}

        return {
            "status": "next_partner_preview",
            "phase": "break",
            "current_round": current_round,
            "next_round": next_round,
            "next_partner": {
                "id": partner.id,
                "nickname": partner.nickname,
            },
        }
    
    else:
        return {"status": "unknown_phase", "current_round": current_round, "phase": current_phase}


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


@app.post("/events/{join_code}/auto_advance")
def auto_advance(join_code: str, session: Session = Depends(get_session)):
    """
    Check if the current phase time has expired and automatically advance to the next phase.
    - If talk phase expired: transition to break, generate next round pairings
    - If break phase expired: transition to next round's talk phase
    """
    event = session.exec(select(Event).where(Event.join_code == join_code)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    current_round = int(event.current_round or 0)
    if current_round <= 0:
        return {"status": "not_started"}

    current_phase = getattr(event, "phase", "talk")
    now = datetime.now(MINSK_TZ)
    phase_ends_at = getattr(event, "phase_ends_at", None)

    if not phase_ends_at:
        return {"status": "no_phase_end_time", "phase": current_phase}

    if phase_ends_at.tzinfo is None:
        phase_ends_at = phase_ends_at.replace(tzinfo=MINSK_TZ)

    # If phase has NOT expired yet
    if phase_ends_at > now:
        seconds_left = int((phase_ends_at - now).total_seconds())
        return {
            "status": "in_progress",
            "phase": current_phase,
            "seconds_left": seconds_left,
            "auto_advanced": False,
        }

    # Phase HAS expired - auto advance

    # If talk phase expired: transition to break and generate next round pairings
    if current_phase == "talk":
        participants = session.exec(
            select(Participant).where(Participant.event_id == event.id)
        ).all()

        if len(participants) < 2:
            raise HTTPException(status_code=400, detail="Not enough participants")

        break_ends_at = now + timedelta(seconds=BREAK_DURATION_SECONDS)
        event.phase = "break"
        event.phase_ends_at = break_ends_at

        # Generate pairings for NEXT round
        next_round_number = int(event.current_round or 0) + 1
        ids = [p.id for p in participants if p.id is not None]
        pairs = make_pairs(
            session=session,
            event_id=event.id,
            participant_ids=ids,
            round_number=next_round_number,
        )

        for p1_id, p2_id in pairs:
            session.add(
                Pairing(
                    event_id=event.id,
                    round_number=next_round_number,
                    p1_id=p1_id,
                    p2_id=p2_id,
                )
            )

        session.add(event)
        session.commit()

        return {
            "status": "advanced",
            "auto_advanced": True,
            "from_phase": "talk",
            "to_phase": "break",
            "current_round": event.current_round,
            "next_round_number": next_round_number,
            "break_ends_at": break_ends_at,
        }

    # If break phase expired: transition to next round's talk phase
    elif current_phase == "break":
        participants = session.exec(
            select(Participant).where(Participant.event_id == event.id)
        ).all()

        if len(participants) < 2:
            raise HTTPException(status_code=400, detail="Not enough participants")

        new_round_number = int(event.current_round or 0) + 1
        started_at = datetime.now(MINSK_TZ)
        ends_at = started_at + timedelta(minutes=8)

        session.add(
            Round(
                event_id=event.id,
                number=new_round_number,
                started_at=started_at,
                ends_at=ends_at,
            )
        )

        event.current_round = new_round_number
        event.phase = "talk"
        event.phase_ends_at = ends_at
        session.add(event)
        session.commit()

        return {
            "status": "advanced",
            "auto_advanced": True,
            "from_phase": "break",
            "to_phase": "talk",
            "new_round": new_round_number,
            "talk_ends_at": ends_at,
        }

    return {"status": "unknown", "phase": current_phase}


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
        # Round record not found; return 0 seconds (stale state)
        return {"phase": "running", "seconds_left": 0, "round": current_round}

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
    now = datetime.now(MINSK_TZ)

    # If currently in talk phase, transition to break and generate next round pairings
    if current_phase == "talk":
        break_ends_at = now + timedelta(seconds=BREAK_DURATION_SECONDS)
        event.phase = "break"
        event.phase_ends_at = break_ends_at
        
        # Generate pairings for NEXT round (participants will see this during break)
        next_round_number = int(event.current_round or 0) + 1
        ids = [p.id for p in participants if p.id is not None]
        pairs = make_pairs(
            session=session,
            event_id=event.id,
            participant_ids=ids,
            round_number=next_round_number,
        )
        
        for p1_id, p2_id in pairs:
            session.add(
                Pairing(
                    event_id=event.id,
                    round_number=next_round_number,
                    p1_id=p1_id,
                    p2_id=p2_id,
                )
            )
        
        session.add(event)
        session.commit()
        return {
            "event_id": event.id,
            "round": event.current_round,
            "phase": "break",
            "started_at": now,
            "ends_at": break_ends_at,
            "message": f"Break started ({BREAK_DURATION_SECONDS} seconds). Pairings for next round generated.",
            "next_round_pairings": len(pairs),
        }

    # If in break phase, validate that break time has elapsed before advancing
    if current_phase == "break":
        break_ends_at = getattr(event, "phase_ends_at", None)
        if break_ends_at:
            # Ensure both are timezone-aware for comparison
            if break_ends_at.tzinfo is None:
                break_ends_at = break_ends_at.replace(tzinfo=MINSK_TZ)
            if break_ends_at > now:
                raise HTTPException(
                    status_code=400,
                    detail=f"Break still in progress. Must wait {int((break_ends_at - now).total_seconds())} more seconds.",
                )

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
        "message": "Transitioned from break to next round's talk phase.",
    }


@app.get("/events/{join_code}/facilitator", response_class=HTMLResponse)
def facilitator_dashboard(join_code: str, session: Session = Depends(get_session)):
    """
    Facilitator dashboard for managing rounds and viewing pairings.
    Returns the facilitator.html template.
    """
    event = session.exec(select(Event).where(Event.join_code == join_code)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    template = jinja_env.get_template("facilitator.html")
    return template.render(title=event.title, join_code=join_code)


@app.get("/events/{join_code}/dashboard")
def dashboard(join_code: str, session: Session = Depends(get_session)):
    """
    Returns JSON with event state, participants, and pairings for real-time updates.
    """
    event = session.exec(select(Event).where(Event.join_code == join_code)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    participants = session.exec(
        select(Participant).where(Participant.event_id == event.id)
    ).all()

    current_round = int(event.current_round or 0)
    pairings = []
    
    if current_round > 0:
        pairings_data = session.exec(
            select(Pairing).where(
                Pairing.event_id == event.id,
                Pairing.round_number == current_round,
            )
        ).all()
        
        for pairing in pairings_data:
            p1 = session.exec(select(Participant).where(Participant.id == pairing.p1_id)).first()
            p2 = session.exec(select(Participant).where(Participant.id == pairing.p2_id)).first() if pairing.p2_id else None
            
            pairings.append({
                "id": pairing.id,
                "p1": {"id": p1.id, "nickname": p1.nickname} if p1 else None,
                "p2": {"id": p2.id, "nickname": p2.nickname} if p2 else None,
                "status": pairing.status,
            })

    # Calculate seconds left
    now = datetime.now(MINSK_TZ)
    phase_ends_at = getattr(event, "phase_ends_at", None)
    seconds_left = 0
    if phase_ends_at:
        if phase_ends_at.tzinfo is None:
            phase_ends_at = phase_ends_at.replace(tzinfo=MINSK_TZ)
        seconds_left = max(0, int((phase_ends_at - now).total_seconds()))

    return {
        "event": {
            "id": event.id,
            "title": event.title,
            "join_code": event.join_code,
            "status": event.status,
            "current_round": current_round,
            "phase": getattr(event, "phase", "lobby"),
            "seconds_left": seconds_left,
        },
        "participants": [
            {"id": p.id, "nickname": p.nickname}
            for p in participants
        ],
        "pairings": pairings,
    }


@app.get("/events/{join_code}/participant_view", response_class=HTMLResponse)
def participant_view(join_code: str, nickname: str, session: Session = Depends(get_session)):
    """
    Participant view showing current partner and round status.
    Returns the participant.html template.
    """
    event = session.exec(select(Event).where(Event.join_code == join_code)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Normalize nickname
    normalized_nickname = nickname.strip().lower()
    
    participant = session.exec(
        select(Participant).where(
            Participant.event_id == event.id, Participant.nickname == normalized_nickname
        )
    ).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    # Sanitize nickname for safe use in HTML
    safe_nickname = normalized_nickname.replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")

    template = jinja_env.get_template("participant.html")
    return template.render(join_code=join_code, safe_nickname=safe_nickname)


@app.post("/events/{join_code}/mark_met")
def mark_met(
    join_code: str, payload: MarkMetRequest, session: Session = Depends(get_session)
):
    """
    Allows a participant to mark that they have met their current partner.
    Updates the pairing status from 'assigned' to 'met'.
    Only allowed during TALK phase.
    """
    event = session.exec(select(Event).where(Event.join_code == join_code)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Check phase: only allow during talk phase
    current_phase = getattr(event, "phase", "talk")
    if current_phase != "talk":
        raise HTTPException(
            status_code=400, 
            detail=f"Can only mark as met during talk phase. Current phase: {current_phase}"
        )

    # Normalize nickname
    normalized_nickname = payload.nickname.strip().lower()
    
    participant = session.exec(
        select(Participant).where(
            Participant.event_id == event.id, Participant.nickname == normalized_nickname
        )
    ).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    current_round = int(event.current_round or 0)
    if current_round <= 0:
        raise HTTPException(status_code=400, detail="No active round")

    pairing = session.exec(
        select(Pairing).where(
            Pairing.event_id == event.id,
            Pairing.round_number == current_round,
            (Pairing.p1_id == participant.id) | (Pairing.p2_id == participant.id),
        )
    ).first()
    if not pairing:
        raise HTTPException(status_code=404, detail="No pairing found for this round")

    pairing.status = "met"
    pairing.met_at = datetime.now(MINSK_TZ)
    session.add(pairing)
    session.commit()
    session.refresh(pairing)

    return {"status": "success", "pairing_id": pairing.id, "met_at": pairing.met_at}


@app.post("/events/{join_code}/upload_questions")
def upload_questions(
    join_code: str,
    payload: QuestionsUploadRequest,
    session: Session = Depends(get_session),
):
    """
    Upload questions for an event (max 50 questions).
    Only allowed before event starts (status != 'running').
    Payload: {"questions": ["Question 1?", "Question 2?", ...]}
    """
    # Validate event exists
    event = session.exec(select(Event).where(Event.join_code == join_code)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Only allow uploading before event is running
    if event.status == "running":
        raise HTTPException(
            status_code=400,
            detail="Cannot upload questions after event has started"
        )
    
    # Validate questions
    is_valid, error_msg = validate_questions_batch(payload.questions)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Delete existing questions if re-uploading
    existing = session.exec(
        select(Question).where(Question.event_id == event.id)
    ).all()
    for q in existing:
        session.delete(q)
    
    # Insert new questions with round_number = 1, 2, 3...
    questions_created = []
    for round_num, question_text in enumerate(payload.questions, start=1):
        question = Question(
            event_id=event.id,
            round_number=round_num,
            text=question_text.strip(),
        )
        session.add(question)
        questions_created.append(question)
    
    session.commit()
    
    return {
        "status": "success",
        "questions_uploaded": len(questions_created),
        "message": f"Successfully uploaded {len(questions_created)} questions"
    }


@app.get("/events/{join_code}/current_question")
def get_current_question(join_code: str, session: Session = Depends(get_session)):
    """
    Get the question for the current round or next round (during break).
    Returns: {"round": 1, "question": "What's your favorite hobby?"}
    or {"status": "no_question"} if round not started or no question for this round
    """
    event = session.exec(select(Event).where(Event.join_code == join_code)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    current_round = int(event.current_round or 0)
    if current_round <= 0:
        return {"status": "no_question", "message": "Event not started yet"}
    
    # During break, show next round's question
    target_round = current_round
    if getattr(event, 'phase', 'talk') == 'break':
        target_round = current_round + 1
    
    question = session.exec(
        select(Question).where(
            Question.event_id == event.id,
            Question.round_number == target_round,
        )
    ).first()
    
    if not question:
        return {
            "status": "no_question",
            "round": target_round,
            "message": "No question for this round"
        }
    
    return {
        "status": "success",
        "round": target_round,
        "question": question.text
    }


@app.get("/events/{join_code}/list_questions")
def list_questions(join_code: str, session: Session = Depends(get_session)):
    """
    List all questions for an event, ordered by round.
    Returns: {"questions": [{"round": 1, "text": "..."}, ...]}
    """
    event = session.exec(select(Event).where(Event.join_code == join_code)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    questions = session.exec(
        select(Question)
        .where(Question.event_id == event.id)
        .order_by(Question.round_number)
    ).all()
    
    return {
        "questions": [
            {"round": q.round_number, "text": q.text}
            for q in questions
        ]
    }
