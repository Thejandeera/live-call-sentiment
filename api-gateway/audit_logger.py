import os
import sys
import json
import time
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if hasattr(record, "audit_data"):
            return json.dumps(record.audit_data, ensure_ascii=False)
        return json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "log_type": "APPLICATION",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage()
        }, ensure_ascii=False)

def setup_audit_logger(service_name: str) -> logging.Logger:
    default_log_dir = str(Path(__file__).resolve().parent.parent / "logs")
    log_dir = os.getenv("LOG_DIR", default_log_dir)
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    max_bytes = int(os.getenv("LOG_MAX_BYTES", 10485760))
    backup_count = int(os.getenv("LOG_BACKUP_COUNT", 10))

    service_log_path = Path(log_dir) / f"{service_name}-logs"
    service_log_path.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(f"audit.{service_name}")
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    logger.propagate = False

    if not logger.handlers:
        formatter = JSONFormatter()
        file_handler = RotatingFileHandler(
            filename=service_log_path / "audit.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger

class AuditLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, service_name: str):
        super().__init__(app)
        self.service_name = service_name
        self.logger = setup_audit_logger(service_name)
        self.environment = os.getenv("LOG_ENVIRONMENT", "development")

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.perf_counter()
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        response = None
        status_code = 500
        outcome = "ERROR"
        try:
            response = await call_next(request)
            status_code = response.status_code
            outcome = "SUCCESS" if status_code < 400 else "FAILURE"
            return response
        except Exception as exc:
            outcome = "ERROR"
            raise exc
        finally:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            audit_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "log_type": "AUDIT",
                "service": self.service_name,
                "environment": self.environment,
                "correlation_id": correlation_id,
                "actor": {
                    "ip": request.client.host if request.client else "unknown",
                    "user_agent": request.headers.get("user-agent", "unknown")
                },
                "request": {
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": dict(request.query_params)
                },
                "response": {
                    "status_code": status_code,
                    "outcome": outcome,
                    "latency_ms": latency_ms
                }
            }
            self.logger.info("", extra={"audit_data": audit_entry})
            if response is not None:
                response.headers["X-Correlation-ID"] = correlation_id
