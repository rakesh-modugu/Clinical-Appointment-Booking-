"""
database.py — SQLAlchemy engine, session factory, and table initialisation
           for the Clinical Appointment Booking Voice Agent.

Database : SQLite  (file: ./appointments.db)
ORM      : SQLAlchemy 2.0 (synchronous session — compatible with FastAPI via
           dependency injection)
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from models.models import Base

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

DATABASE_URL = "sqlite:///./appointments.db"

engine = create_engine(
    DATABASE_URL,
    # Required for SQLite when the same connection is reused across threads
    # (FastAPI runs request handlers in a thread pool).
    connect_args={"check_same_thread": False},
    echo=False,           # Set True to log SQL statements during development
    pool_pre_ping=True,   # Verify connection liveness before each checkout
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,   # Explicit flush control — prevents accidental mid-tx flushes
    autocommit=False,  # Always use explicit transactions
    expire_on_commit=False,  # Keep ORM objects usable after commit
)

# ---------------------------------------------------------------------------
# FastAPI dependency: yields a DB session and guarantees close on exit
# ---------------------------------------------------------------------------

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a SQLAlchemy Session per request.

    Usage in a route:
        def my_endpoint(db: Session = Depends(get_db)): ...

    The session is committed automatically on clean exit and rolled back
    on any exception, then closed in the finally block regardless.
    """
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

# ---------------------------------------------------------------------------
# Table creation (call once at startup)
# ---------------------------------------------------------------------------

def init_db() -> None:
    """
    Create all tables defined in Base.metadata if they do not already exist.
    Safe to call on every application startup (CREATE TABLE IF NOT EXISTS).
    """
    Base.metadata.create_all(bind=engine)
