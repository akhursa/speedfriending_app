import secrets as secrets_mod
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from config import config
from db import get_session
from dependencies import get_event, verify_pin, jinja_env
from models import Event, Participant, Pairing, PairHistory, Round, Question, MINSK_TZ
from schemas import QuestionsUploadRequest
from services.pairing import make_pairs
from services.photo import photo_service
from validators import validate_questions_batch

router = APIRouter()


# ── Pages ────────────────────────────────────────────────────────────


@router.get("/facilitator/login", response_class=HTMLResponse)
def facilitator_login():
    template = jinja_env.get_template("facilitator_login.html")
    return template.render()


@router.get("/events/{join_code}/facilitator", response_class=HTMLResponse)
def facilitator_dashboard_page(
    event: Event = Depends(get_event),
):
    template = jinja_env.get_template("facilitator.html")
    return template.render(title=event.title, join_code=event.join_code)


# ── Auth ─────────────────────────────────────────────────────────────


@router.post("/events/{join_code}/verify_facilitator")
def verify_facilitator(
    join_code: str,
    pin: str = Query(..., description="Facilitator PIN"),
    session: Session = Depends(get_session),
):
    event = session.exec(
        select(Event).where(Event.join_code == join_code.strip().upper())
    ).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if not event.facilitator_pin or not secrets_mod.compare_digest(
        event.facilitator_pin, pin
    ):
        raise HTTPException(status_code=403, detail="Invalid facilitator PIN")

    return {"status": "authenticated", "join_code": join_code}


# ── Dashboard data (PIN-protected) ───────────────────────────────────


@router.get("/events/{join_code}/dashboard")
def dashboard(
    event: Event = Depends(verify_pin),
    session: Session = Depends(get_session),
):
    current_round = int(event.current_round or 0)
    participants = session.exec(
        select(Participant).where(Participant.event_id == event.id)
    ).all()

    participant_map = {p.id: p for p in participants}
    pairings = []

    if current_round > 0:
        pairings_data = session.exec(
            select(Pairing).where(
                Pairing.event_id == event.id,
                Pairing.round_number == current_round,
            )
        ).all()

        for pairing in pairings_data:
            p1 = participant_map.get(pairing.p1_id)
            p2 = participant_map.get(pairing.p2_id) if pairing.p2_id else None

            pairings.append(
                {
                    "id": pairing.id,
                    "p1": {"id": p1.id, "nickname": p1.nickname} if p1 else None,
                    "p2": {"id": p2.id, "nickname": p2.nickname} if p2 else None,
                    "status": pairing.status,
                }
            )

    now = datetime.now(MINSK_TZ)
    phase_ends_at = event.phase_ends_at
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
            "phase": event.phase,
            "seconds_left": seconds_left,
        },
        "participants": [{"id": p.id, "nickname": p.nickname} for p in participants],
        "pairings": pairings,
    }


# ── Round management (PIN-protected) ────────────────────────────────


@router.post("/events/{join_code}/start_round")
def start_round(
    event: Event = Depends(verify_pin),
    session: Session = Depends(get_session),
):
    current_round = int(event.current_round or 0)
    if current_round > 0:
        raise HTTPException(
            status_code=400, detail="Event already started. Use /next_round."
        )

    participants = session.exec(
        select(Participant).where(Participant.event_id == event.id)
    ).all()
    if len(participants) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 participants")

    next_round_num = current_round + 1
    event.current_round = next_round_num
    event.status = "running"

    started_at = datetime.now(MINSK_TZ)
    ends_at = started_at + timedelta(minutes=config.TALK_DURATION_MINUTES)

    event.phase = "talk"
    event.phase_ends_at = ends_at

    session.add(
        Round(
            event_id=event.id,
            number=next_round_num,
            started_at=started_at,
            ends_at=ends_at,
        )
    )

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


@router.post("/events/{join_code}/next_round")
def next_round(
    event: Event = Depends(verify_pin),
    session: Session = Depends(get_session),
):
    if not event.current_round or event.current_round <= 0:
        raise HTTPException(
            status_code=400, detail="Event not started yet. Use /start_round."
        )

    participants = session.exec(
        select(Participant).where(Participant.event_id == event.id)
    ).all()
    if len(participants) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 participants")

    current_phase = event.phase
    now = datetime.now(MINSK_TZ)

    if current_phase == "talk":
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
            "event_id": event.id,
            "round": event.current_round,
            "phase": "break",
            "started_at": now,
            "ends_at": break_ends_at,
            "message": f"Break started ({config.BREAK_DURATION_SECONDS} seconds). Pairings for next round generated.",
            "next_round_pairings": len(pairs),
        }

    if current_phase == "break":
        break_ends_at = event.phase_ends_at
        if break_ends_at:
            if break_ends_at.tzinfo is None:
                break_ends_at = break_ends_at.replace(tzinfo=MINSK_TZ)
            if break_ends_at > now:
                raise HTTPException(
                    status_code=400,
                    detail=f"Break still in progress. Must wait {int((break_ends_at - now).total_seconds())} more seconds.",
                )

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


# ── End event (PIN-protected) ────────────────────────────────────────


@router.post("/events/{join_code}/end_event")
def end_event(
    event: Event = Depends(verify_pin),
    session: Session = Depends(get_session),
):
    event.status = "ended"
    event.phase = "ended"
    session.add(event)
    session.commit()
    return {"status": "success", "message": "Event ended"}


# ── Questions management (PIN-protected) ─────────────────────────────


@router.post("/events/{join_code}/upload_questions")
def upload_questions(
    payload: QuestionsUploadRequest,
    event: Event = Depends(verify_pin),
    session: Session = Depends(get_session),
):
    if event.status == "running":
        raise HTTPException(
            status_code=400, detail="Cannot upload questions after event has started"
        )

    is_valid, error_msg = validate_questions_batch(payload.questions)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    existing = session.exec(
        select(Question).where(Question.event_id == event.id)
    ).all()
    for q in existing:
        session.delete(q)

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
        "message": f"Successfully uploaded {len(questions_created)} questions",
    }


# ── Delete participant (PIN-protected) ───────────────────────────────


@router.delete("/events/{join_code}/participants/{nickname}")
def delete_participant(
    nickname: str,
    event: Event = Depends(verify_pin),
    session: Session = Depends(get_session),
):
    nickname = nickname.strip().lower()
    participant = session.exec(
        select(Participant).where(
            Participant.event_id == event.id, Participant.nickname == nickname
        )
    ).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    participant_id = participant.id

    if participant.photo_filename:
        photo_service.delete_photo(participant.photo_filename)

    pairings = session.exec(
        select(Pairing).where(
            (Pairing.event_id == event.id)
            & ((Pairing.p1_id == participant_id) | (Pairing.p2_id == participant_id))
        )
    ).all()
    for pairing in pairings:
        session.delete(pairing)

    pair_histories = session.exec(
        select(PairHistory).where(
            (PairHistory.event_id == event.id)
            & (
                (PairHistory.a_id == participant_id)
                | (PairHistory.b_id == participant_id)
            )
        )
    ).all()
    for ph in pair_histories:
        session.delete(ph)

    session.delete(participant)
    session.commit()

    return {
        "status": "success",
        "message": f"Participant '{nickname}' removed from event",
    }
