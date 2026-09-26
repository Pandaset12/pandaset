"""Request correlation and structured failure logs without secret-bearing messages."""
from contextvars import ContextVar
import json
import logging
from pathlib import Path
import traceback

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
logger = logging.getLogger("portfoliolens")


def log_failure(code: str, exc: Exception) -> None:
    frames = [
        {"file": Path(frame.filename).name, "line": frame.lineno, "function": frame.name}
        for frame in traceback.extract_tb(exc.__traceback__)
    ]
    logger.warning(json.dumps({
        "event": "request_failure",
        "request_id": request_id_context.get(),
        "code": code,
        "exception_type": type(exc).__name__,
        "cause_type": type(exc.__cause__).__name__ if exc.__cause__ else None,
        "frames": frames,
    }))
