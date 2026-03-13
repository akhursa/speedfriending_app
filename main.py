from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv()

from config import config
from db import create_db_and_tables
from routers import events, participants, facilitator

app = FastAPI(
    title="Speed Friending API",
    description="Real-time speed dating event management platform",
    version="1.0.0",
)

# Static files
static_dir = Path(config.PHOTO_UPLOAD_DIR)
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_HOSTS if config.is_production() else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

if config.is_production():
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=config.ALLOWED_HOSTS,
    )

# Routers
app.include_router(events.router)
app.include_router(participants.router)
app.include_router(facilitator.router)


@app.on_event("startup")
def on_startup():
    import models  # noqa: F401 – ensure tables are registered

    create_db_and_tables()
