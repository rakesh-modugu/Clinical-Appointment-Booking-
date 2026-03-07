"""Transcript ORM model — stores each conversation turn per session."""

from sqlalchemy import String, Text, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import Base, TimestampMixin, generate_uuid


class Transcript(Base, TimestampMixin):
    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("voice_sessions.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20))          # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    audio_url: Mapped[str] = mapped_column(String, nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=True)

    session: Mapped["VoiceSession"] = relationship(back_populates="transcripts")
