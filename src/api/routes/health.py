"""
Health Check Routes - System health and monitoring endpoints.

These endpoints are used for:
1. Load balancer health checks
2. Kubernetes liveness/readiness probes
3. Monitoring systems
4. Quick system status verification
"""
from datetime import datetime

from fastapi import APIRouter

from src.core.config import get_settings
from src.core.logging_config import get_logger
from src.models.chat import HealthResponse

logger = get_logger(__name__)

router = APIRouter(
    prefix="/health",
    tags=["Health"],
)

# Application version - would typically come from package metadata
APP_VERSION = "0.1.0"


@router.get(
    "",
    response_model=HealthResponse,
    summary="Health check endpoint",
    description="""
    Returns the current health status of the service.
    
    Use this endpoint for:
    - Load balancer health checks
    - Kubernetes probes
    - Monitoring dashboards
    
    Returns 200 OK if the service is healthy.
    """
)
async def health_check() -> HealthResponse:
    """
    Perform a basic health check.
    
    This endpoint verifies that the API is running and responsive.
    It does not check database or LLM connectivity (those would
    be separate readiness checks in production).
    """
    logger.debug("Health check requested")
    
    return HealthResponse(
        status="healthy",
        version=APP_VERSION,
        timestamp=datetime.utcnow()
    )


@router.get(
    "/ready",
    response_model=HealthResponse,
    summary="Readiness check endpoint",
    description="""
    Returns whether the service is ready to accept requests.
    
    In Phase 1, this is identical to the health check.
    In later phases, this will verify:
    - Database connectivity
    - LLM service availability
    - Memory system status
    """
)
async def readiness_check() -> HealthResponse:
    """
    Perform a readiness check.
    
    Verifies that the service is ready to handle requests.
    Currently identical to health check; will be extended
    in later phases to include dependency checks.
    """
    logger.debug("Readiness check requested")
    
    settings = get_settings()
    
    return HealthResponse(
        status="ready",
        version=APP_VERSION,
        timestamp=datetime.utcnow()
    )
