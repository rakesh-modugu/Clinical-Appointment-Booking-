"""
tools.py — LLM-callable tool definitions for agentic reasoning and DB orchestration.
======================================================================================

This module exposes the clinical appointment tools to the OpenAI function-calling
API. The LLM decides WHEN and WHY to call each tool based on conversation context;
this module handles HOW — routing the call to real database operations.

Integration pattern
-------------------
  1. Pass `OPENAI_TOOLS` to `client.chat.completions.create(tools=OPENAI_TOOLS)`.
  2. When the LLM returns a `tool_calls` response, extract `function.name` and
     `function.arguments` (JSON string) for each call.
  3. Pass them to `execute_tool_call(name, args)` to get a string result.
  4. Append the result as a `{"role": "tool", "content": result}` message and
     continue the completion to get the agent's final natural-language reply.
"""

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError

from database import SessionLocal
from models.models import Appointment, Doctor, Patient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _parse_dt(dt_str: str) -> datetime:
    """Parse an ISO-8601 datetime string, with or without timezone suffix."""
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(dt_str.rstrip("Z"), fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse datetime string: {dt_str!r}")


# ---------------------------------------------------------------------------
# Tool 1: get_doctor_availability
# ---------------------------------------------------------------------------

async def get_doctor_availability(doctor_id: str) -> str:
    """
    Query the database for a doctor's booked slots and return their availability.

    Returns a JSON string describing:
      - Doctor details (name, specialization, is_available flag)
      - List of BOOKED and RESCHEDULED appointments (start/end times, status)

    The LLM uses this output to reason about which time slots are free before
    suggesting an appointment time to the patient.
    """
    db = SessionLocal()
    try:
        doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
        if not doctor:
            return json.dumps({
                "error": f"Doctor with id '{doctor_id}' not found.",
                "available_slots": [],
            })

        active_appointments = (
            db.query(Appointment)
            .filter(
                Appointment.doctor_id == doctor_id,
                Appointment.status.in_(["Booked", "Rescheduled"]),
                Appointment.start_time >= datetime.utcnow(),  # Future only
            )
            .order_by(Appointment.start_time)
            .all()
        )

        booked_slots = [
            {
                "appointment_id": appt.id,
                "start_time":     appt.start_time.isoformat(),
                "end_time":       appt.end_time.isoformat(),
                "status":         appt.status,
            }
            for appt in active_appointments
        ]

        result = {
            "doctor_id":        doctor.id,
            "doctor_name":      doctor.name,
            "specialization":   doctor.specialization,
            "is_available":     doctor.is_available,
            "booked_slots":     booked_slots,
            "booked_slot_count": len(booked_slots),
            "message": (
                f"Dr. {doctor.name} has {len(booked_slots)} upcoming booked slot(s)."
                if doctor.is_available
                else f"Dr. {doctor.name} is currently marked as unavailable."
            ),
        }
        return json.dumps(result, default=str)

    except Exception as exc:
        logger.error("get_doctor_availability error: doctor_id=%s  error=%s", doctor_id, exc)
        return json.dumps({"error": f"Database error: {str(exc)}"})
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool 2: book_appointment_tool
# ---------------------------------------------------------------------------

async def book_appointment_tool(
    patient_id: str,
    doctor_id: str,
    start_time: str,
    end_time: str,
) -> str:
    """
    Attempt to insert a new appointment row into the database.

    Conflict handling (two layers)
    --------------------------------
    1. Application-level overlap query: checks for existing BOOKED/RESCHEDULED
       appointments whose time window intersects the requested slot.
       Returns a descriptive message so the LLM can suggest an alternative.

    2. DB-level UniqueConstraint on (doctor_id, start_time): last-resort guard
       against race conditions — surfaced as a 409-style JSON error string.

    Returns a JSON string that the LLM incorporates into its spoken reply.
    """
    db = SessionLocal()
    try:
        start_dt = _parse_dt(start_time)
        end_dt   = _parse_dt(end_time)
    except ValueError as exc:
        return json.dumps({"error": f"Invalid datetime format: {exc}"})

    try:
        # --- Validate patient ---
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            return json.dumps({"error": f"Patient '{patient_id}' not found."})

        # --- Validate doctor ---
        doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
        if not doctor:
            return json.dumps({"error": f"Doctor '{doctor_id}' not found."})
        if not doctor.is_available:
            return json.dumps({
                "error": f"Dr. {doctor.name} is currently unavailable for new bookings."
            })

        # --- Application-level overlap check ---
        overlap = (
            db.query(Appointment)
            .filter(
                Appointment.doctor_id == doctor_id,
                Appointment.status.in_(["Booked", "Rescheduled"]),
                and_(
                    Appointment.start_time < end_dt,
                    Appointment.end_time   > start_dt,
                ),
            )
            .first()
        )
        if overlap:
            return json.dumps({
                "error": "slot_conflict",
                "message": (
                    f"Dr. {doctor.name} is already booked from "
                    f"{overlap.start_time.strftime('%Y-%m-%d %H:%M')} to "
                    f"{overlap.end_time.strftime('%H:%M')}. "
                    "Please choose a different time."
                ),
                "conflicting_slot": {
                    "start_time": overlap.start_time.isoformat(),
                    "end_time":   overlap.end_time.isoformat(),
                },
            })

        # --- Insert appointment ---
        import uuid
        new_appt = Appointment(
            id=str(uuid.uuid4()),
            patient_id=patient_id,
            doctor_id=doctor_id,
            start_time=start_dt,
            end_time=end_dt,
            status="Booked",
        )
        db.add(new_appt)
        db.flush()   # Trigger DB constraints before commit
        db.commit()

        return json.dumps({
            "success":        True,
            "appointment_id": new_appt.id,
            "doctor_name":    doctor.name,
            "patient_name":   patient.name,
            "start_time":     new_appt.start_time.isoformat(),
            "end_time":       new_appt.end_time.isoformat(),
            "status":         new_appt.status,
            "message": (
                f"Appointment successfully booked with Dr. {doctor.name} "
                f"on {new_appt.start_time.strftime('%B %d at %I:%M %p')}."
            ),
        })

    except IntegrityError:
        db.rollback()
        return json.dumps({
            "error": "db_conflict",
            "message": (
                "A booking conflict was detected at the database level (concurrent request). "
                "Please try a different time slot."
            ),
        })
    except Exception as exc:
        db.rollback()
        logger.error("book_appointment_tool error: %s", exc)
        return json.dumps({"error": f"Database error: {str(exc)}"})
    finally:
        db.close()


# ---------------------------------------------------------------------------
# OpenAI Function-Calling Schema
# ---------------------------------------------------------------------------

OPENAI_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_doctor_availability",
            "description": (
                "Query the clinical database to check a specific doctor's availability. "
                "Returns the doctor's details, whether they are currently accepting patients, "
                "and a list of all upcoming booked time slots. Use this BEFORE suggesting a "
                "time to the patient to avoid proposing an already-booked slot."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {
                        "type": "string",
                        "description": (
                            "The UUID of the doctor to check. "
                            "Obtain this from previous context or ask the patient which doctor they prefer."
                        ),
                    }
                },
                "required": ["doctor_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment_tool",
            "description": (
                "Book a clinical appointment by inserting a confirmed slot into the database. "
                "ONLY call this after the patient has explicitly confirmed the doctor, date, and time. "
                "This function handles double-booking conflicts and returns a success confirmation "
                "or a descriptive conflict message with an alternative suggestion."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "string",
                        "description": "UUID of the patient making the booking.",
                    },
                    "doctor_id": {
                        "type": "string",
                        "description": "UUID of the doctor being booked.",
                    },
                    "start_time": {
                        "type": "string",
                        "description": (
                            "Start datetime of the appointment in ISO-8601 format "
                            "(e.g., '2026-03-10T10:30:00'). Must be in the future."
                        ),
                    },
                    "end_time": {
                        "type": "string",
                        "description": (
                            "End datetime of the appointment in ISO-8601 format "
                            "(e.g., '2026-03-10T11:00:00'). Must be after start_time."
                        ),
                    },
                },
                "required": ["patient_id", "doctor_id", "start_time", "end_time"],
                "additionalProperties": False,
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Tool Dispatcher
# ---------------------------------------------------------------------------

_TOOL_REGISTRY: dict[str, Any] = {
    "get_doctor_availability": get_doctor_availability,
    "book_appointment_tool":   book_appointment_tool,
}


async def execute_tool_call(function_name: str, arguments: dict[str, Any]) -> str:
    """
    Route an LLM tool-call request to the corresponding Python function
    and return its JSON string result.

    Parameters
    ----------
    function_name : Name of the function as declared in OPENAI_TOOLS.
    arguments     : Dict of parsed arguments (from JSON-decoded `function.arguments`).

    Returns
    -------
    A JSON string — appended as a `{"role": "tool", "content": <str>}` message
    in the conversation before the LLM generates its spoken reply.

    Usage example
    -------------
    >>> tool_result = await execute_tool_call(
    ...     "book_appointment_tool",
    ...     {
    ...         "patient_id": "...",
    ...         "doctor_id":  "...",
    ...         "start_time": "2026-03-10T10:30:00",
    ...         "end_time":   "2026-03-10T11:00:00",
    ...     }
    ... )
    >>> # Append to messages and continue LLM completion
    """
    fn = _TOOL_REGISTRY.get(function_name)
    if fn is None:
        logger.warning("Unknown tool called by LLM: %s", function_name)
        return json.dumps({
            "error": f"Unknown tool '{function_name}'. "
                     f"Available tools: {list(_TOOL_REGISTRY.keys())}"
        })

    try:
        logger.info("Executing tool: %s  args=%s", function_name, arguments)
        result: str = await fn(**arguments)
        logger.info("Tool result: %s  → %s", function_name, result[:120])
        return result
    except TypeError as exc:
        # Argument mismatch — LLM passed wrong param names
        logger.error("Tool argument error: %s  error=%s", function_name, exc)
        return json.dumps({
            "error": f"Invalid arguments for '{function_name}': {str(exc)}"
        })
    except Exception as exc:
        logger.error("Tool execution error: %s  error=%s", function_name, exc)
        return json.dumps({"error": f"Tool execution failed: {str(exc)}"})
