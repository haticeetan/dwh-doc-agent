import json
import logging
import os
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

# Her HTTP isteği kendi UUID'sini buraya yazar.
# contextvars sayesinde eşzamanlı istekler birbirinin değerini ezmez.
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")


class _JsonFormatter(logging.Formatter):
    """Her log satırını tek bir JSON nesnesine dönüştürür (ELK/Splunk uyumlu)."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id.get(),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def setup_logging() -> None:
    """
    Uygulama başlangıcında bir kez çağrılır (main.py).
    LOG_LEVEL ortam değişkeniyle seviye ayarlanabilir; varsayılan INFO.
    """
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Her modül bu fonksiyonla kendi logger'ını alır."""
    return logging.getLogger(name)
