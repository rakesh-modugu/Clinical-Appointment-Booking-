"""
main.py — FastAPI application entry point for the Clinical Appointment
          Booking Voice Agent.

Endpoints
---------
  POST /book-appointment  — Validates input, detects overlapping slots,
                            and persists a new appointment row.
  GET  /health            — Liveness probe.
"""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db, init_db
from models.models import Appointment, Doctor, Patient

# ---------------------------------------------------------------------------
# App initialisation
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Clinical Appointment Booking — Voice AI Backend",
    version="1.0.0",
    description="Real-time multilingual voice agent API for booking, cancelling, and rescheduling clinical appointments.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    """Create all DB tables on first run."""
    init_db()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class AppointmentCreate(BaseModel):
    """
    Input schema for POST /book-appointment.

    All fields are required. `start_time` must be strictly before `end_time`
    and both must be in the future at the time of submission.
    """
    patient_id: str
    doctor_id: str
    start_time: datetime
    end_time: datetime

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def parse_datetime(cls, v: str | datetime) -> datetime:
        if isinstance(v, str):
            return datetime.fromisoformat(v)
        return v

    @model_validator(mode="after")
    def validate_time_range(self) -> "AppointmentCreate":
        if self.start_time >= self.end_time:
            raise ValueError("`start_time` must be strictly before `end_time`.")
        if self.start_time < datetime.utcnow():
            raise ValueError("Cannot book an appointment in the past.")
        return self


class AppointmentResponse(BaseModel):
    """Successful booking confirmation payload."""
    appointment_id: str
    patient_id: str
    doctor_id: str
    start_time: datetime
    end_time: datetime
    status: str
    message: str

    model_config = {"from_attributes": True}


class HealthResponse(BaseModel):
    status: str
    db: str


# ---------------------------------------------------------------------------
# Helper: overlap detection query
# ---------------------------------------------------------------------------

def _has_overlapping_appointment(
    db: Session,
    doctor_id: str,
    start_time: datetime,
    end_time: datetime,
    exclude_appointment_id: str | None = None,
) -> bool:
    """
    Return True if the doctor already has a BOOKED (or RESCHEDULED) appointment
    that overlaps with [start_time, end_time).

    Overlap condition (two intervals A and B overlap when):
        A.start < B.end  AND  A.end > B.start

    The `exclude_appointment_id` parameter is used during rescheduling so the
    original appointment is not counted as a conflict with itself.
    """
    query = db.query(Appointment).filter(
        Appointment.doctor_id == doctor_id,
        Appointment.status.in_(["Booked", "Rescheduled"]),
        # Overlap: existing.start_time < new.end_time AND existing.end_time > new.start_time
        and_(
            Appointment.start_time < end_time,
            Appointment.end_time > start_time,
        ),
    )

    if exclude_appointment_id:
        query = query.filter(Appointment.id != exclude_appointment_id)

    return db.query(query.exists()).scalar()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Infrastructure"],
    summary="Liveness probe",
)
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    """Returns 200 when the API and database are reachable."""
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "unreachable"
    return HealthResponse(status="ok", db=db_status)


@app.post(
    "/book-appointment",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Appointments"],
    summary="Book a new clinical appointment",
)
def book_appointment(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
) -> AppointmentResponse:
    """
    Books a new appointment after validating:

    1. **Patient exists** — 404 if patient_id is unknown.
    2. **Doctor exists and is available** — 404 / 409 accordingly.
    3. **No overlapping slots** — 400 with a clear message if the doctor is
       already booked for any part of the requested time window.
    4. **DB-level uniqueness** — The UniqueConstraint on (doctor_id, start_time)
       acts as a hard last-resort guard against race conditions; any resulting
       IntegrityError is surfaced as a 409.
    """

    # --- 1. Verify patient ---
    patient = db.query(Patient).filter(Patient.id == payload.patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient '{payload.patient_id}' not found.",
        )

    # --- 2. Verify doctor ---
    doctor = db.query(Doctor).filter(Doctor.id == payload.doctor_id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Doctor '{payload.doctor_id}' not found.",
        )
    if not doctor.is_available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Dr. {doctor.name} is currently marked as unavailable.",
        )

    # --- 3. Application-level overlap check (friendly, pre-write) ---
    if _has_overlapping_appointment(
        db,
        doctor_id=payload.doctor_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Dr. {doctor.name} already has an appointment that overlaps with "
                f"{payload.start_time.strftime('%Y-%m-%d %H:%M')} – "
                f"{payload.end_time.strftime('%H:%M')}. "
                "Please choose a different time slot."
            ),
        )

    # --- 4. Create and persist the appointment ---
    new_appointment = Appointment(
        id=str(uuid.uuid4()),
        patient_id=payload.patient_id,
        doctor_id=payload.doctor_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
        status="Booked",
    )

    db.add(new_appointment)

    try:
        db.flush()   # Flush to DB within the transaction to catch constraint violations
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A booking conflict was detected at the database level "
                "(concurrent request). Please retry."
            ),
        )

    return AppointmentResponse(
        appointment_id=new_appointment.id,
        patient_id=new_appointment.patient_id,
        doctor_id=new_appointment.doctor_id,
        start_time=new_appointment.start_time,
        end_time=new_appointment.end_time,
        status=new_appointment.status,
        message=f"Appointment successfully booked with Dr. {doctor.name}.",
    )
