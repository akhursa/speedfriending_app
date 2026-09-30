from sqlalchemy import event as sa_event
from sqlmodel import SQLModel, Session, create_engine
from config import config

DATABASE_URL = config.get_database_url()

# SQLAlchemy требует схему postgresql://, а некоторые сервисы возвращают postgres://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL.startswith("postgresql"):
    # PostgreSQL engine
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,  # Verify connection before using
        pool_recycle=3600,   # Recycle connections every hour
    )

    # Установка часового пояса для каждого нового соединения с БД
    @sa_event.listens_for(engine, "connect")
    def _set_session_tz(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("SET TIME ZONE 'Europe/Minsk'")
        cur.close()
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
