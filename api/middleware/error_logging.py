"""
Error logging middleware: loguje każde HTTP 500 z pełnym stack trace.

CO: Middleware FastAPI przechwytujący nieobsłużone wyjątki i odpowiedzi 500.
PO CO: Bez tego błędy 500 w docker logs są lakoniczne lub pomijane.
       Pełny stack trace pozwala diagnozować problemy bez SSH na VPS.
       Umożliwia też opcjonalne poszerzone logowanie gdy DEBUG_MODE=true.
JAK: Klasa Starlette BaseHTTPMiddleware. Wrapuje każde request/response.
     Jeśli response.status_code >= 500 — loguje ERROR z pełną traceback.
     Jeśli DEBUG_MODE (z env lub app_settings) — loguje INFO każdy request.
"""
import logging
import traceback
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("vse.error")


class ErrorLoggingMiddleware(BaseHTTPMiddleware):
    """
    CO: Middleware logujący wszystkie błędy HTTP 5xx i opcjonalnie każdy request w trybie debug.
    PO CO: `docker logs vse-api` pokazuje pełny stack trace dla każdego 500.
    JAK: Dziedziczy po BaseHTTPMiddleware Starlette. Rejestrowany w api/main.py.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Intercept request/response, log errors and debug info."""
        debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"

        if debug_mode:
            logger.info("[DEBUG] %s %s", request.method, request.url.path)

        try:
            response = await call_next(request)
        except Exception as exc:
            # Unhandled exception — log with full traceback
            logger.error(
                "Unhandled exception on %s %s:\n%s",
                request.method,
                request.url.path,
                traceback.format_exc(),
            )
            raise

        if response.status_code >= 500:
            logger.error(
                "HTTP %s on %s %s",
                response.status_code,
                request.method,
                request.url.path,
            )

        return response
