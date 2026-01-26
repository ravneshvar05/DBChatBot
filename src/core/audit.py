"""
Audit Middleware - Request/response logging for monitoring and compliance.

This middleware logs all API requests including:
- Request method and path
- Response status code
- Request duration
- Session ID (if available)

Logs are written to the application log file.
"""
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.core.logging_config import get_logger

logger = get_logger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging all requests and responses.
    
    Captures timing information and key request metadata
    for debugging and compliance purposes.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log audit information."""
        start_time = time.time()
        
        # Extract useful metadata
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"
        
        # Try to get session_id from query params or will be in body
        session_id = request.query_params.get("session_id", "")[:8] or "-"
        
        try:
            # Process the request
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log the request
            self._log_request(
                method=method,
                path=path,
                status_code=response.status_code,
                duration=duration,
                client_ip=client_ip,
                session_id=session_id
            )
            
            # Add timing header
            response.headers["X-Response-Time"] = f"{duration:.3f}s"
            
            return response
            
        except Exception as e:
            # Log failed requests too
            duration = time.time() - start_time
            logger.error(
                f"REQUEST FAILED: {method} {path} "
                f"client={client_ip} duration={duration:.3f}s error={str(e)}"
            )
            raise
    
    def _log_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration: float,
        client_ip: str,
        session_id: str
    ) -> None:
        """Log request details."""
        # Skip health checks from verbose logging
        if path in ("/health", "/health/ready"):
            logger.debug(
                f"HEALTH: {path} status={status_code} duration={duration:.3f}s"
            )
            return
        
        # Determine log level based on status code
        if status_code >= 500:
            log_fn = logger.error
        elif status_code >= 400:
            log_fn = logger.warning
        else:
            log_fn = logger.info
        
        log_fn(
            f"REQUEST: {method} {path} "
            f"status={status_code} duration={duration:.3f}s "
            f"client={client_ip} session={session_id}"
        )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.
    
    Headers added:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Referrer-Policy: strict-origin-when-cross-origin
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response
