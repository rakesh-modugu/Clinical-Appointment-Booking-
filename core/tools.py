"""
tools.py — DB-backed tool functions for the clinical voice agent's agentic loop.

These functions are what the LLM actually calls to interact with the SQLite
database. Keep them simple and easy to trace in the terminal logs.
"""

import json
import logging
import uuid
from datetime import datetime

from sqlalchemy import and_

from database import SessionLocal
from models.models import Appointment, Doctor, Patient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared datetime parser
# ---------------------------------------------------------------------------

def _parse_dt(s: str) -> datetime:
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s.rstrip("Z"), fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse datetime: {s!r}")


# ---------------------------------------------------------------------------
# Tool 1: check_doctor_availability
# ---------------------------------------------------------------------------

def check_doctor_availability(doctor_name: str, requested_time: str) -> str:
    """
    Check whether a doctor exists and has no overlapping bookings at the
    requested time. Assumes a default 30-minute slot if only a start time
    is provided.

    Returns a plain-English string the LLM can speak directly to the patient.
    """
    db = SessionLocal()
    try:
        # Find doctor by name (case-insensitive partial match)
        doctor = (
            db.query(Doctor)
            .filter(Doctor.name.ilike(f"%{doctor_name}%"))
            .first()
        )
        if not doctor:
            return f"Sorry, I couldn't find a doctor named '{doctor_name}' in the system."

        if not doctor.is_available:
            return f"Dr. {doctor.name} is currently marked as unavailable for new bookings."

        start_dt = _parse_dt(requested_time)
        # Default slot length: 30 minutes
        from datetime import timedelta
        end_dt = start_dt + timedelta(minutes=30)

        conflict = (
            db.query(Appointment)
            .filter(
                Appointment.doctor_id == doctor.id,
                Appointment.status.in_(["Booked", "Rescheduled"]),
                and_(
                    Appointment.start_time < end_dt,
                    Appointment.end_time   > start_dt,
                ),
            )
            .first()
        )

        if conflict:
            return (
                f"Dr. {doctor.name} is already booked from "
                f"{conflict.start_time.strftime('%I:%M %p')} to "
                f"{conflict.end_time.strftime('%I:%M %p')} on "
                f"{conflict.start_time.strftime('%B %d')}. Please choose a different time."
            )

        return (
            f"Dr. {doctor.name} ({doctor.specialization}) is available at "
            f"{start_dt.strftime('%I:%M %p on %B %d, %Y')}."
        )

    except ValueError as exc:
        return f"Invalid time format provided: {exc}"
    except Exception as exc:
        logger.error("check_doctor_availability error: %s", exc)
        return "I ran into a database error while checking availability. Please try again."
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool 2: book_appointment_tool
# ---------------------------------------------------------------------------

def book_appointment_tool(
    patient_phone: str,
    doctor_name: str,
    start_time: str,
    end_time: str,
) -> str:
    """
    Book an appointment by looking up the patient via phone number and the
    doctor by name, then inserting a new Appointment row.

    Returns a confirmation string (or a conflict/error message) that the
    LLM converts into a natural spoken reply.
    """
    db = SessionLocal()
    try:
        # Look up patient by phone number
        patient = (
            db.query(Patient)
            .filter(Patient.phone_number == patient_phone)
            .first()
        )
        if not patient:
            return (
                f"I couldn't find a patient registered with phone number {patient_phone}. "
                "Please register first."
            )

        # Look up doctor by name
        doctor = (
            db.query(Doctor)
            .filter(Doctor.name.ilike(f"%{doctor_name}%"))
            .first()
        )
        if not doctor:
            return f"I couldn't find a doctor named '{doctor_name}' in the system."

        if not doctor.is_available:
            return f"Dr. {doctor.name} is currently unavailable for new bookings."

        start_dt = _parse_dt(start_time)
        end_dt   = _parse_dt(end_time)

        if start_dt >= end_dt:
            return "The start time must be before the end time. Please provide a valid time range."

        # Check for overlap before inserting
        conflict = (
            db.query(Appointment)
            .filter(
                Appointment.doctor_id == doctor.id,
                Appointment.status.in_(["Booked", "Rescheduled"]),
                and_(
                    Appointment.start_time < end_dt,
                    Appointment.end_time   > start_dt,
                ),
            )
            .first()
        )
        if conflict:
            return (
                f"Sorry, Dr. {doctor.name} is already booked from "
                f"{conflict.start_time.strftime('%I:%M %p')} to "
                f"{conflict.end_time.strftime('%I:%M %p')}. "
                "Please pick a different time."
            )

        # Insert the appointment
        new_appt = Appointment(
            id=str(uuid.uuid4()),
            patient_id=patient.id,
            doctor_id=doctor.id,
            start_time=start_dt,
            end_time=end_dt,
            status="Booked",
        )
        db.add(new_appt)
        db.commit()

        logger.info(
            "Appointment booked: patient=%s doctor=%s start=%s",
            patient.name, doctor.name, start_dt,
        )

        return (
            f"Done! I've booked an appointment for {patient.name} with "
            f"Dr. {doctor.name} ({doctor.specialization}) on "
            f"{start_dt.strftime('%B %d, %Y')} from "
            f"{start_dt.strftime('%I:%M %p')} to {end_dt.strftime('%I:%M %p')}. "
            f"Appointment ID: {new_appt.id[:8].upper()}."
        )

    except ValueError as exc:
        return f"Invalid time format: {exc}"
    except Exception as exc:
        db.rollback()
        logger.error("book_appointment_tool error: %s", exc)
        return "A database error occurred while booking the appointment. Please try again."
    finally:
        db.close()


# ---------------------------------------------------------------------------
# OpenAI Function-Calling Schema
# ---------------------------------------------------------------------------

OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_doctor_availability",
            "description": (
                "Check if a specific doctor is available at a requested time. "
                "Call this BEFORE suggesting or confirming any appointment slot. "
                "Returns a plain-English availability status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_name": {
                        "type": "string",
                        "description": "The name (or partial name) of the doctor to check.",
                    },
                    "requested_time": {
                        "type": "string",
                        "description": (
                            "The requested appointment start time in ISO-8601 format "
                            "(e.g., '2026-03-10T10:30:00')."
                        ),
                    },
                },
                "required": ["doctor_name", "requested_time"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment_tool",
            "description": (
                "Book a clinical appointment in the database. "
                "ONLY call this after the patient has explicitly confirmed the doctor, date, and time. "
                "Looks up the patient by phone number and the doctor by name."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_phone": {
                        "type": "string",
                        "description": "The patient's registered phone number (used to identify them).",
                    },
                    "doctor_name": {
                        "type": "string",
                        "description": "The name (or partial name) of the doctor to book.",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Appointment start time in ISO-8601 format (e.g., '2026-03-10T10:30:00').",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "Appointment end time in ISO-8601 format (e.g., '2026-03-10T11:00:00').",
                    },
                },
                "required": ["patient_phone", "doctor_name", "start_time", "end_time"],
                "additionalProperties": False,
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Tool Dispatcher
# ---------------------------------------------------------------------------

_REGISTRY = {
    "check_doctor_availability": check_doctor_availability,
    "book_appointment_tool":     book_appointment_tool,
}


async def execute_tool_call(function_name: str, arguments: dict) -> str:
    """
    Route the LLM's tool call to the correct Python function and return
    its string result. The result is appended as a tool-role message so
    the LLM can incorporate the DB response into its spoken reply.
    """
    fn = _REGISTRY.get(function_name)
    if fn is None:
        logger.warning("LLM called unknown tool: %s", function_name)
        return f"Unknown tool '{function_name}'. Available: {list(_REGISTRY.keys())}"

    try:
        logger.info("Executing tool: %s  args=%s", function_name, arguments)
        result = fn(**arguments)   # Tools are sync — call directly
        logger.info("Tool result [%s]: %s", function_name, result)
        return result
    except TypeError as exc:
        logger.error("Wrong arguments for tool %s: %s", function_name, exc)
        return f"Tool call failed — wrong arguments: {exc}"
    except Exception as exc:
        logger.error("Tool execution error [%s]: %s", function_name, exc)
        return f"Tool execution failed: {exc}"
