"""Voice session ORM model — tracks per-session metadata."""

from sqlalchemy import String, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import Base, TimestampMixin, generate_uuid


class VoiceSession(Base, TimestampMixin):
    __tablename__ = "voice_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="started")  # started | ended | error
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=True)
    total_tokens: Mapped[int] = mapped_column(default=0)

    user: Mapped["User"] = relationship(back_populates="sessions")
    transcripts: Mapped[list["Transcript"]] = relationship(back_populates="session")
