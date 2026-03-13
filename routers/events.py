import secrets
import string
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlmodel import Session, select

from config import config
from db import get_session
from dependencies import get_event, jinja_env
from models import (
    Event,
    Participant,
    Pairing,
    PairHistory,
    Round,
    Question,
    MINSK_TZ,
)
from schemas import EventCreate, EventResponse
from validators import validate_event_title

router = APIRouter()


def _generate_join_code(n: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def _generate_facilitator_pin(n: int = 4) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(n))


# ── Pages ────────────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
def read_root():
    template = jinja_env.get_template("index.html")
    return template.render()


@router.get("/join", response_class=HTMLResponse)
def join_page(code: str = None):
    template = jinja_env.get_template("join.html")
    return template.render()


# ── Event CRUD ───────────────────────────────────────────────────────


@router.post("/events", response_model=EventResponse)
def create_event(payload: EventCreate, session: Session = Depends(get_session)):
    is_valid, error_msg = validate_event_title(payload.title)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    join_code = _generate_join_code()
    while session.exec(select(Event).where(Event.join_code == join_code)).first():
        join_code = _generate_join_code()

    facilitator_pin = _generate_facilitator_pin()

    event = Event(
        title=payload.title.strip(),
        join_code=join_code,
        facilitator_pin=facilitator_pin,
    )
    session.add(event)
    session.commit()
    session.refresh(event)

    return EventResponse(
        id=event.id,
        title=event.title,
        join_code=event.join_code,
        facilitator_pin=event.facilitator_pin,
        created_at=event.created_at.isoformat(),
        status=event.status,
    )


# ── Public event endpoints ───────────────────────────────────────────


@router.get("/events/{join_code}/info")
def event_info(
    event: Event = Depends(get_event),
    session: Session = Depends(get_session),
):
    participant_count = session.exec(
        select(func.count(Participant.id)).where(Participant.event_id == event.id)
    ).one()

    total_pairings = session.exec(
        select(func.count(Pairing.id)).where(Pairing.event_id == event.id)
    ).one()

    total_unique_pairs = session.exec(
        select(func.count(PairHistory.id)).where(PairHistory.event_id == event.id)
    ).one()

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


@router.get("/events/{join_code}/state")
def event_state(
    event: Event = Depends(get_event),
    session: Session = Depends(get_session),
):
    participants_count = session.exec(
        select(func.count(Participant.id)).where(Participant.event_id == event.id)
    ).one()

    current_round = int(event.current_round or 0)

    ends_at = event.phase_ends_at
    if ends_at is None and current_round > 0:
        round_row = session.exec(
            select(Round).where(
                Round.event_id == event.id, Round.number == current_round
            )
        ).first()
        if round_row:
            ends_at = round_row.ends_at

    now = datetime.now(MINSK_TZ)
    if ends_at is not None and ends_at.tzinfo is None:
        ends_at = ends_at.replace(tzinfo=MINSK_TZ)

    seconds_left = 0
    if ends_at:
        seconds_left = max(0, int((ends_at - now).total_seconds()))

    pairings_count = 0
    if current_round > 0:
        pairings_count = session.exec(
            select(func.count(Pairing.id)).where(
                Pairing.event_id == event.id,
                Pairing.round_number == current_round,
            )
        ).one()

    return {
        "join_code": event.join_code,
        "status": event.status,
        "current_round": current_round,
        "phase": event.phase,
        "seconds_left": seconds_left,
        "participants_count": participants_count,
        "pairings_count": pairings_count,
    }


@router.get("/events/{join_code}/timer")
def event_timer(
    event: Event = Depends(get_event),
    session: Session = Depends(get_session),
):
    current_round = int(event.current_round or 0)
    if current_round <= 0:
        return {"phase": "lobby", "seconds_left": None, "round": 0}

    round_obj = session.exec(
        select(Round).where(Round.event_id == event.id, Round.number == current_round)
    ).first()
    if not round_obj:
        return {"phase": "running", "seconds_left": 0, "round": current_round}

    now = datetime.now(MINSK_TZ)
    ends_at = round_obj.ends_at
    if ends_at.tzinfo is None:
        ends_at = ends_at.replace(tzinfo=MINSK_TZ)

    seconds_left = max(0, int((ends_at - now).total_seconds()))

    return {
        "phase": "running",
        "seconds_left": seconds_left,
        "round": event.current_round,
    }


# ── Questions (read-only, public) ────────────────────────────────────


@router.get("/events/{join_code}/current_question")
def get_current_question(
    event: Event = Depends(get_event),
    session: Session = Depends(get_session),
):
    current_round = int(event.current_round or 0)
    if current_round <= 0:
        return {"status": "no_question", "message": "Event not started yet"}

    target_round = current_round
    if event.phase == "break":
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
            "message": "No question for this round",
        }

    return {"status": "success", "round": target_round, "question": question.text}


@router.get("/events/{join_code}/list_questions")
def list_questions(
    event: Event = Depends(get_event),
    session: Session = Depends(get_session),
):
    questions = session.exec(
        select(Question)
        .where(Question.event_id == event.id)
        .order_by(Question.round_number)
    ).all()

    return {"questions": [{"round": q.round_number, "text": q.text} for q in questions]}


# ── Auto-advance (called by participant polling) ─────────────────────


@router.post("/events/{join_code}/auto_advance")
def auto_advance(
    event: Event = Depends(get_event),
    session: Session = Depends(get_session),
):
    current_round = int(event.current_round or 0)
    if current_round <= 0:
        return {"status": "not_started"}

    current_phase = event.phase
    now = datetime.now(MINSK_TZ)
    phase_ends_at = event.phase_ends_at

    if not phase_ends_at:
        return {"status": "no_phase_end_time", "phase": current_phase}

    if phase_ends_at.tzinfo is None:
        phase_ends_at = phase_ends_at.replace(tzinfo=MINSK_TZ)

    if phase_ends_at > now:
        seconds_left = int((phase_ends_at - now).total_seconds())
        return {
            "status": "in_progress",
            "phase": current_phase,
            "seconds_left": seconds_left,
            "auto_advanced": False,
        }

    # Re-read event to guard against concurrent transitions
    session.refresh(event)
    if event.phase != current_phase:
        return {"status": "already_advanced", "phase": event.phase, "auto_advanced": False}

    from services.pairing import make_pairs

    if current_phase == "talk":
        participants = session.exec(
            select(Participant).where(Participant.event_id == event.id)
        ).all()
        if len(participants) < 2:
            raise HTTPException(status_code=400, detail="Not enough participants")

        break_ends_at = now + timedelta(seconds=config.BREAK_DURATION_SECONDS)
        event.phase = "break"
        event.phase_ends_at = break_ends_at

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

    elif current_phase == "break":
        participants = session.exec(
            select(Participant).where(Participant.event_id == event.id)
        ).all()
        if len(participants) < 2:
            raise HTTPException(status_code=400, detail="Not enough participants")

        new_round_number = int(event.current_round or 0) + 1
        started_at = datetime.now(MINSK_TZ)
        ends_at = started_at + timedelta(minutes=config.TALK_DURATION_MINUTES)

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
