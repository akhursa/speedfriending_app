"""
Configuration management for Speed Friending application.
Loads settings from environment variables with fallbacks for local development.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration"""

    # Environment
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    DEBUG = ENVIRONMENT == "development"

    # Database
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "sqlite:///database.db" if ENVIRONMENT == "development" else None,
    )

    if not DATABASE_URL:
        raise ValueError("DATABASE_URL must be set in production environment")

    # Timing
    BREAK_DURATION_SECONDS = int(os.getenv("BREAK_DURATION_SECONDS", "60"))
    TALK_DURATION_MINUTES = int(os.getenv("TALK_DURATION_MINUTES", "5"))

    # Security
    SECRET_KEY = os.getenv("SECRET_KEY")
    if ENVIRONMENT == "production" and not SECRET_KEY:
        raise ValueError("SECRET_KEY must be set in production environment")
    if not SECRET_KEY:
        SECRET_KEY = "dev-secret-key-change-in-production"

    # Hosting
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))

    # CORS
    ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

    # Photo storage
    PHOTO_UPLOAD_DIR = os.getenv("PHOTO_UPLOAD_DIR", "static/uploads/photos")
    PHOTO_MAX_SIZE_MB = float(os.getenv("PHOTO_MAX_SIZE_MB", "5.0"))

    @classmethod
    def get_database_url(cls):
        """Return appropriate database URL for the environment"""
        return cls.DATABASE_URL

    @classmethod
    def is_production(cls):
        """Check if running in production"""
        return cls.ENVIRONMENT == "production"

    @classmethod
    def is_development(cls):
        """Check if running in development"""
        return cls.ENVIRONMENT == "development"


# Export config instance
config = Config()
