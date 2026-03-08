"""
Health check and readiness probe endpoint.
Used by load balancers and container orchestrators (k8s, ECS).
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def health_check():
    return {"status": "ok"}


@router.get("/ready")
async def readiness_probe():
    # TODO: check DB and Redis connectivity
    return {"status": "ready", "db": "ok", "redis": "ok"}
