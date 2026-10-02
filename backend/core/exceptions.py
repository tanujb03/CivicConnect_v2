from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from typing import Any, Dict, Optional


class CivicConnectException(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: Optional[Dict[str, Any]] = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def _envelope(request: Request, code: str, message: str, details: Any = None) -> Dict[str, Any]:
    """The one error shape of design §51A.1: {error: {code, message, details, request_id}}."""
    return {"error": {"code": code, "message": message, "details": details or {},
                      "request_id": getattr(request.state, "request_id", None)}}


async def civicconnect_exception_handler(request: Request, exc: CivicConnectException):
    return JSONResponse(status_code=exc.status_code, content=_envelope(request, exc.code, exc.message, exc.details))


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Framework/auth errors also use the envelope. The legacy ``detail`` key is kept alongside so existing clients/tests keep working."""
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        code, message, details = str(detail["code"]), str(detail.get("message", "")), {k: v for k, v in detail.items() if k not in ("code", "message")}
    else:
        code, message, details = f"HTTP_{exc.status_code}", str(detail), {}
    body = _envelope(request, code, message, details)
    body["detail"] = detail
    return JSONResponse(status_code=exc.status_code, content=body, headers=getattr(exc, "headers", None))


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [{"loc": list(e.get("loc", [])), "message": e.get("msg", ""), "type": e.get("type", "")} for e in exc.errors()]
    body = _envelope(request, "VALIDATION_ERROR", "The request is invalid.", {"errors": errors})
    body["detail"] = [{"loc": list(e.get("loc", [])), "msg": e.get("msg", ""), "type": e.get("type", "")} for e in exc.errors()]
    return JSONResponse(status_code=422, content=body)
