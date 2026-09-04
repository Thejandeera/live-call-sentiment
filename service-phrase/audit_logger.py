import os
import sys
import re
import json
import time
import uuid
import logging
import threading
from pathlib import Path
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
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


class StdoutTee:
    _lock = threading.Lock()
    ANSI_REGEX = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    def __init__(self, original_stream, handler):
        self.original_stream = original_stream
        self.handler = handler
        self.dummy_record = logging.LogRecord("", logging.INFO, "", 0, "", (), None)
        self._buffer = ""

    def write(self, message):
        self.original_stream.write(message)
        try:
            with StdoutTee._lock:
                clean = self.ANSI_REGEX.sub('', message).replace('\r', '')
                if not clean:
                    return
                self._buffer += clean
                if '\n' in self._buffer:
                    lines = self._buffer.split('\n')
                    self._buffer = lines[-1]
                    to_write = '\n'.join(lines[:-1]) + '\n'
                    if self.handler.shouldRollover(self.dummy_record):
                        self.handler.doRollover()
                    if self.handler.stream:
                        self.handler.stream.write(to_write)
                        self.handler.stream.flush()
        except Exception:
            pass

    def flush(self):
        self.original_stream.flush()
        try:
            with StdoutTee._lock:
                if self._buffer and self.handler.stream:
                    self.handler.stream.write(self._buffer)
                    self.handler.stream.flush()
                    self._buffer = ""
        except Exception:
            pass


_app_log_setup_done = False

def setup_app_logging(service_name: str):
    global _app_log_setup_done
    if _app_log_setup_done:
        return
    _app_log_setup_done = True

    default_log_dir = str(Path(__file__).resolve().parent.parent / "logs")
    log_dir = os.getenv("LOG_DIR", default_log_dir)
    backup_days = int(os.getenv("LOG_BACKUP_DAYS", 30))
    service_log_path = Path(log_dir) / f"{service_name}-logs"
    
    try:
        service_log_path.mkdir(parents=True, exist_ok=True)
        file_handler = TimedRotatingFileHandler(
            filename=service_log_path / "app.log",
            when="midnight",
            interval=1,
            backupCount=backup_days,
            encoding="utf-8",
            utc=True
        )
        file_handler.suffix = "%Y-%m-%d.log"
        file_handler.extMatch = re.compile(r"^\d{4}-\d{2}-\d{2}\.log$")
        
        sys.stdout = StdoutTee(sys.stdout, file_handler)
        sys.stderr = StdoutTee(sys.stderr, file_handler)
    except Exception as e:
        sys.stderr.write(f"[AppLogger] Note: App logging disabled ({e}).\n")


def setup_audit_logger(service_name: str) -> logging.Logger:
    setup_app_logging(service_name)
    default_log_dir = str(Path(__file__).resolve().parent.parent / "logs")
    log_dir = os.getenv("LOG_DIR", default_log_dir)
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    backup_days = int(os.getenv("LOG_BACKUP_DAYS", 30))

    service_log_path = Path(log_dir) / f"{service_name}-logs"

    logger = logging.getLogger(f"audit.{service_name}")
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    logger.propagate = False

    if not logger.handlers:
        formatter = JSONFormatter()
        try:
            service_log_path.mkdir(parents=True, exist_ok=True)
            file_handler = TimedRotatingFileHandler(
                filename=service_log_path / "audit.log",
                when="midnight",
                interval=1,
                backupCount=backup_days,
                encoding="utf-8",
                utc=True
            )
            file_handler.suffix = "%Y-%m-%d.log"
            file_handler.extMatch = re.compile(r"^\d{4}-\d{2}-\d{2}\.log$")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            sys.stderr.write(f"[AuditLogger] Note: File logging disabled ({e}). Outputting to stdout.\n")

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
