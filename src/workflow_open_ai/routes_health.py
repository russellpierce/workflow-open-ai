import logging
from typing import Final

from fastapi import APIRouter
from pydantic import BaseModel

logger: Final = logging.getLogger(__name__)
router: Final = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str = "healthy"


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Health check endpoint. No authentication required."""
    logger.debug("Health check requested")
    return HealthResponse(status="healthy")
