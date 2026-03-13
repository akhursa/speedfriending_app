from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from config import config
from db import get_session
from dependencies import get_event, jinja_env
from models import Event, Participant, Pairing, MINSK_TZ
from schemas import JoinRequest, MarkMetRequest
from services.photo import photo_service
from validators import validate_nickname, validate_join_code

router = APIRouter()


# ── Pages ────────────────────────────────────────────────────────────


@router.get("/events/{join_code}/participant_view", response_class=HTMLResponse)
def participant_view(
    join_code: str,
    nickname: str,
    session: Session = Depends(get_session),
):
    event = session.exec(
        select(Event).where(Event.join_code == join_code.strip().upper())
    ).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    normalized_nickname = nickname.strip().lower()
    participant = session.exec(
        select(Participant).where(
            Participant.event_id == event.id,
            Participant.nickname == normalized_nickname,
        )
    ).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    safe_nickname = (
        normalized_nickname.replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    template = jinja_env.get_template("participant.html")
    return template.render(join_code=join_code, safe_nickname=safe_nickname)


# ── Join / List ──────────────────────────────────────────────────────


@router.post("/events/{join_code}/join")
def join_event(
    join_code: str,
    payload: JoinRequest,
    session: Session = Depends(get_session),
):
    code_valid, code_error = validate_join_code(join_code)
    if not code_valid:
        raise HTTPException(status_code=400, detail=code_error)

    nickname_valid, nickname_error = validate_nickname(payload.nickname)
    if not nickname_valid:
        raise HTTPException(status_code=400, detail=nickname_error)

    normalized_nickname = payload.nickname.strip().lower()

    event = session.exec(
        select(Event).where(Event.join_code == join_code.strip().upper())
    ).first()
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
        event_id=event.id, nickname=normalized_nickname, email=payload.email
    )
    session.add(participant)
    session.commit()
    session.refresh(participant)

    return {
        "id": participant.id,
        "event_id": participant.event_id,
        "nickname": participant.nickname,
        "email": participant.email,
        "photo_filename": participant.photo_filename,
        "photo_uploaded_at": participant.photo_uploaded_at,
        "joined_at": participant.joined_at,
        "photo_url": None,
    }


@router.get("/events/{join_code}/participants")
def list_participants(
    event: Event = Depends(get_event),
    session: Session = Depends(get_session),
):
    participants = session.exec(
        select(Participant).where(Participant.event_id == event.id)
    ).all()

    return {
        "event_id": event.id,
        "join_code": event.join_code,
        "participants": [
            {
                "id": p.id,
                "nickname": p.nickname,
                "email": p.email,
                "photo_filename": p.photo_filename,
                "photo_url": photo_service.get_photo_url(p.photo_filename),
                "joined_at": p.joined_at,
            }
            for p in participants
        ],
    }


# ── Photo upload ─────────────────────────────────────────────────────


@router.post("/events/{join_code}/upload_photo")
async def upload_photo(
    join_code: str,
    nickname: str,
    photo: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    event = session.exec(
        select(Event).where(Event.join_code == join_code.strip().upper())
    ).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    normalized_nickname = nickname.strip().lower()
    participant = session.exec(
        select(Participant).where(
            Participant.event_id == event.id,
            Participant.nickname == normalized_nickname,
        )
    ).first()
    if not participant:
        raise HTTPException(
            status_code=404, detail="Participant not found in this event"
        )

    if not photo.content_type or not photo.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed")

    contents = await photo.read()

    is_valid, error_msg = photo_service.validate_photo(
        contents, config.PHOTO_MAX_SIZE_MB
    )
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    extension = "jpg"
    if photo.content_type == "image/png":
        extension = "png"

    if participant.photo_filename:
        photo_service.delete_photo(participant.photo_filename)

    filename = photo_service.save_photo(contents, extension)
    participant.photo_filename = filename
    participant.photo_uploaded_at = datetime.now()
    session.add(participant)
    session.commit()
    session.refresh(participant)

    return {
        "success": True,
        "photo_url": photo_service.get_photo_url(filename),
    }


# ── Match / Met ──────────────────────────────────────────────────────


@router.get("/events/{join_code}/my_match")
def my_match(
    nickname: str,
    event: Event = Depends(get_event),
    session: Session = Depends(get_session),
):
    normalized_nickname = nickname.strip().lower()
    participant = session.exec(
        select(Participant).where(
            Participant.event_id == event.id,
            Participant.nickname == normalized_nickname,
        )
    ).first()
    if not participant:
        raise HTTPException(
            status_code=404, detail="Participant not found in this event"
        )

    current_round = int(event.current_round or 0)
    if current_round <= 0:
        return {"status": "waiting", "current_round": 0}

    current_phase = event.phase

    if current_phase == "talk":
        pairing = session.exec(
            select(Pairing).where(
                Pairing.event_id == event.id,
                Pairing.round_number == current_round,
                (Pairing.p1_id == participant.id) | (Pairing.p2_id == participant.id),
            )
        ).first()

        if not pairing:
            return {
                "status": "no_pair",
                "current_round": current_round,
                "phase": "talk",
            }

        partner_id = (
            pairing.p2_id if pairing.p1_id == participant.id else pairing.p1_id
        )

        if partner_id is None:
            return {
                "status": "no_pair",
                "current_round": current_round,
                "phase": "talk",
            }

        partner = session.exec(
            select(Participant).where(Participant.id == partner_id)
        ).first()
        if not partner:
            return {
                "status": "no_pair",
                "current_round": current_round,
                "phase": "talk",
            }

        return {
            "status": "paired",
            "phase": "talk",
            "current_round": current_round,
            "partner": {
                "id": partner.id,
                "nickname": partner.nickname,
                "photo_url": photo_service.get_photo_url(partner.photo_filename),
            },
        }

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
            return {
                "status": "waiting_for_pairing",
                "phase": "break",
                "current_round": current_round,
            }

        partner_id = (
            next_pairing.p2_id
            if next_pairing.p1_id == participant.id
            else next_pairing.p1_id
        )

        if partner_id is None:
            return {
                "status": "resting",
                "phase": "break",
                "current_round": current_round,
                "next_round": next_round,
            }

        partner = session.exec(
            select(Participant).where(Participant.id == partner_id)
        ).first()
        if not partner:
            return {
                "status": "waiting_for_pairing",
                "phase": "break",
                "current_round": current_round,
            }

        return {
            "status": "next_partner_preview",
            "phase": "break",
            "current_round": current_round,
            "next_round": next_round,
            "next_partner": {
                "id": partner.id,
                "nickname": partner.nickname,
                "photo_url": photo_service.get_photo_url(partner.photo_filename),
            },
        }

    elif current_phase == "ended":
        return {
            "status": "ended",
            "current_round": current_round,
            "phase": "ended",
        }

    return {
        "status": "unknown_phase",
        "current_round": current_round,
        "phase": current_phase,
    }


@router.post("/events/{join_code}/mark_met")
def mark_met(
    payload: MarkMetRequest,
    event: Event = Depends(get_event),
    session: Session = Depends(get_session),
):
    if event.phase != "talk":
        raise HTTPException(
            status_code=400,
            detail=f"Can only mark as met during talk phase. Current phase: {event.phase}",
        )

    normalized_nickname = payload.nickname.strip().lower()
    participant = session.exec(
        select(Participant).where(
            Participant.event_id == event.id,
            Participant.nickname == normalized_nickname,
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
