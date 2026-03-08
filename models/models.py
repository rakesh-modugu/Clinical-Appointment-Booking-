"""
models.py — Core data layer for the Real-Time Multilingual Voice AI Agent
          for Clinical Appointment Booking.

SQLite (Long-term Persistent Memory)
-------------------------------------
  Tables: patients, doctors, appointments

Redis (Short-term Contextual Memory)
--------------------------------------
  See REDIS_SESSION_SCHEMA docstring at the bottom of this file.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    create_engine,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)

# ---------------------------------------------------------------------------
# Engine + Session factory (SQLite default; swap URL for Postgres in prod)
# ---------------------------------------------------------------------------

DATABASE_URL = "sqlite:///./clinical_agent.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite + async use
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


# ---------------------------------------------------------------------------
# Declarative Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """
    Shared declarative base for all ORM models.
    All tables inherit from this to participate in metadata registration.
    """
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _new_uuid() -> str:
    """Generate a new UUID4 string. Used as the default for primary keys."""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Model: Patient
# ---------------------------------------------------------------------------

LANGUAGE_CHECK = "language_preference IN ('English', 'Hindi', 'Tamil')"


class Patient(Base):
    """
    Represents a patient registered in the clinical voice-agent system.

    Identification is driven by `phone_number` — the voice agent resolves
    returning patients via their phone number, removing the need for any
    web-authentication mechanism.

    language_preference is strictly constrained at the DB level to one of
    the three supported locales ('English', 'Hindi', 'Tamil') so that the
    TTS/STT pipeline always receives a known value and never falls through
    to an unsupported locale.
    """

    __tablename__ = "patients"

    __table_args__ = (
        CheckConstraint(LANGUAGE_CHECK, name="ck_patient_language"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
        doc="UUID primary key — generated on insert.",
    )
    phone_number: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
        doc="E.164-formatted phone number. Uniquely identifies returning patients.",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Full name of the patient as provided during registration.",
    )
    language_preference: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="English",
        doc="Preferred response language. Constrained to: 'English', 'Hindi', 'Tamil'.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp of patient record creation (UTC).",
    )

    # Relationships
    appointments: Mapped[List["Appointment"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
        doc="All appointments belonging to this patient.",
    )

    def __repr__(self) -> str:
        return f"<Patient id={self.id!r} phone={self.phone_number!r} lang={self.language_preference!r}>"


# ---------------------------------------------------------------------------
# Model: Doctor
# ---------------------------------------------------------------------------

class Doctor(Base):
    """
    Represents a clinician available for appointment booking.

    `is_available` acts as a soft toggle: the voice agent checks this flag
    before offering a doctor to a patient. Setting it to False (e.g., due to
    leave) prevents new bookings without deleting existing records.
    """

    __tablename__ = "doctors"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
        doc="UUID primary key.",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Full name of the doctor.",
    )
    specialization: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Medical specialization (e.g., 'Cardiology', 'General Practice').",
    )
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="Whether the doctor is available for new bookings.",
    )

    # Relationships
    appointments: Mapped[List["Appointment"]] = relationship(
        back_populates="doctor",
        cascade="all, delete-orphan",
        doc="All appointments assigned to this doctor.",
    )

    def __repr__(self) -> str:
        return (
            f"<Doctor id={self.id!r} name={self.name!r} "
            f"spec={self.specialization!r} available={self.is_available}>"
        )


# ---------------------------------------------------------------------------
# Model: Appointment
# ---------------------------------------------------------------------------

APPOINTMENT_STATUS_CHECK = "status IN ('Booked', 'Cancelled', 'Rescheduled')"


class Appointment(Base):
    """
    Links a Patient to a Doctor for a specific time slot.

    Double-booking prevention is enforced at two levels:
      1. UniqueConstraint on (doctor_id, start_time) — DB-level hard guard.
         Any concurrent INSERT for the same doctor + start_time will raise
         an IntegrityError that the service layer must catch and surface to
         the voice agent as a "slot unavailable" response.
      2. Application-level availability check before INSERT (service layer),
         giving the agent a user-friendly denial before hitting the DB.

    `status` is constrained to exactly three values reflecting the
    appointment lifecycle: Booked → (Rescheduled | Cancelled).
    """

    __tablename__ = "appointments"

    __table_args__ = (
        UniqueConstraint(
            "doctor_id",
            "start_time",
            name="uq_doctor_start_time",
        ),
        CheckConstraint(APPOINTMENT_STATUS_CHECK, name="ck_appointment_status"),
        # Composite index for fast slot-availability range queries
        Index("ix_appointments_doctor_time_range", "doctor_id", "start_time", "end_time"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
        doc="UUID primary key.",
    )
    patient_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        doc="FK → patients.id. The patient who booked this appointment.",
    )
    doctor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        doc="FK → doctors.id. The doctor assigned to this appointment.",
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        doc="Start datetime of the appointment slot (UTC).",
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        doc="End datetime of the appointment slot (UTC).",
    )
    status: Mapped[str] = mapped_column(
        String(15),
        nullable=False,
        default="Booked",
        doc="Lifecycle status. One of: 'Booked', 'Cancelled', 'Rescheduled'.",
    )

    # Relationships
    patient: Mapped["Patient"] = relationship(
        back_populates="appointments",
        doc="The patient who owns this appointment.",
    )
    doctor: Mapped["Doctor"] = relationship(
        back_populates="appointments",
        doc="The doctor assigned to this appointment.",
    )

    def __repr__(self) -> str:
        return (
            f"<Appointment id={self.id!r} status={self.status!r} "
            f"patient={self.patient_id!r} doctor={self.doctor_id!r} "
            f"start={self.start_time!r}>"
        )


# ---------------------------------------------------------------------------
# Table creation helper (dev / testing)
# ---------------------------------------------------------------------------

def create_all_tables() -> None:
    """Create all tables in the bound SQLite database. Safe to call on startup."""
    Base.metadata.create_all(bind=engine)


# ---------------------------------------------------------------------------
# Redis Short-Term Contextual Memory Schema
# ---------------------------------------------------------------------------

REDIS_SESSION_SCHEMA: dict = {
    "__doc__": """
    Redis Session Context Schema
    ============================
    Each active voice session stores its context under the key:

        KEY FORMAT :  session:<session_id>
        DATA TYPE  :  Redis JSON (via RedisJSON module) or serialised JSON string
        TTL        :  1800 seconds (30 minutes).
                      The TTL is reset on EVERY agent turn so that an active
                      conversation never expires mid-flow.
                      On explicit session-end (hang-up / user says "goodbye"),
                      the key is deleted immediately rather than waiting for TTL.

    Field Definitions
    -----------------
    session_id          : str   — UUID of the active voice session. Mirrors the key.
    patient_id          : str   — UUID of the resolved Patient record (from SQLite).
                                  NULL until the caller is identified via phone_number.
    current_intent      : str   — The intent the agent is currently fulfilling.
                                  Possible values:
                                    "booking"     — patient wants a new appointment
                                    "cancelling"  — patient wants to cancel
                                    "rescheduling"— patient wants to reschedule
                                    "enquiring"   — patient wants info (doctor, slot)
                                    "greeting"    — session just started, intent unclear
                                    "farewell"    — session wrapping up
    pending_confirmation: bool  — True when the agent has proposed an action
                                  (e.g., "Book Dr. Ravi at 10am?") and is waiting
                                  for the patient's explicit yes/no.
                                  Reset to False after any confirmation or denial.
    extracted_entities  : dict  — Slot values collected so far this session.
                                  {
                                    "doctor_name"    : str | None,
                                    "specialization" : str | None,
                                    "preferred_date" : str | None,  # ISO-8601 date
                                    "preferred_time" : str | None,  # "HH:MM"
                                    "appointment_id" : str | None   # UUID, for cancel/reschedule
                                  }
    conversation_state  : list  — Ordered list of the last N turns (N ≤ 10 to cap
                                  Redis memory usage). Each turn is a dict:
                                  {
                                    "role"      : "user" | "agent",
                                    "content"   : str,   # Transcript text
                                    "timestamp" : str    # ISO-8601 UTC datetime
                                  }
    language            : str   — Active session language, inherited from Patient
                                  language_preference. One of: 'English', 'Hindi', 'Tamil'.
                                  Controls STT model variant and TTS voice selection.
    """,

    # ---- Concrete example value stored in Redis ----
    "session_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "patient_id": "3d721e9a-1c2b-4a3f-9b8e-dc12e3456789",
    "current_intent": "booking",
    "pending_confirmation": False,
    "extracted_entities": {
        "doctor_name": "Dr. Priya Ramesh",
        "specialization": "Cardiology",
        "preferred_date": "2026-03-10",
        "preferred_time": "10:30",
        "appointment_id": None,
    },
    "conversation_state": [
        {
            "role": "user",
            "content": "I want to book an appointment with a cardiologist.",
            "timestamp": "2026-03-07T10:00:01Z",
        },
        {
            "role": "agent",
            "content": "Sure! Dr. Priya Ramesh is available on March 10th at 10:30 AM. Shall I confirm?",
            "timestamp": "2026-03-07T10:00:03Z",
        },
    ],
    "language": "English",
}
