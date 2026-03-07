"""
Shared FastAPI dependency injectors.
Provides DB sessions, current user extraction, and Redis client access.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import decode_access_token
from models.base import async_session_factory

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/sessions/token")


async def get_db() -> AsyncSession:
    """Yield an async SQLAlchemy session and close it after use."""
    async with async_session_factory() as session:
        yield session


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Decode JWT and return the authenticated user payload."""
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return payload
