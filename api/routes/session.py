"""
REST endpoints for starting, ending, and listing voice sessions.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user

router = APIRouter()


@router.post("/start")
async def start_session(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Create a new voice session and return its ID."""
    # TODO: insert session row into DB and return session_id
    return {"session_id": "placeholder-uuid", "status": "started"}


@router.post("/{session_id}/end")
async def end_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Mark a session as ended and persist final metadata."""
    # TODO: update session row status → ended
    return {"session_id": session_id, "status": "ended"}


@router.get("/")
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Return all past sessions for the current user."""
    # TODO: query DB for sessions belonging to user
    return {"sessions": []}
