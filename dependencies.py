import secrets as secrets_mod
from pathlib import Path

from fastapi import Depends, HTTPException, Query
from jinja2 import Environment, FileSystemLoader
from sqlmodel import Session, select

from db import get_session
from models import Event

templates_dir = Path(__file__).parent / "templates"
jinja_env = Environment(loader=FileSystemLoader(str(templates_dir)))


def get_event(join_code: str, session: Session = Depends(get_session)) -> Event:
    """Resolve event by join_code path parameter. Raises 404 if not found."""
    event = session.exec(
        select(Event).where(Event.join_code == join_code.strip().upper())
    ).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


def verify_pin(
    join_code: str,
    pin: str = Query(..., description="Facilitator PIN"),
    session: Session = Depends(get_session),
) -> Event:
    """Resolve event and verify facilitator PIN. Raises 403 on mismatch."""
    event = session.exec(
        select(Event).where(Event.join_code == join_code.strip().upper())
    ).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if not event.facilitator_pin or not secrets_mod.compare_digest(
        event.facilitator_pin, pin
    ):
        raise HTTPException(status_code=403, detail="Invalid facilitator PIN")
    return event
