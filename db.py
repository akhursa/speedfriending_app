from sqlmodel import SQLModel, Session, create_engine
from config import config

DATABASE_URL = config.get_database_url()

# Create engine with appropriate connection arguments
if "postgresql" in DATABASE_URL or "postgres" in DATABASE_URL:
    # PostgreSQL engine
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,  # Verify connection before using
        pool_recycle=3600,   # Recycle connections every hour
    )
else:
    # SQLite engine for development
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )


def create_db_and_tables():
    """Create all database tables based on SQLModel definitions"""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Yield database session for dependency injection"""
    with Session(engine) as session:
        yield session

