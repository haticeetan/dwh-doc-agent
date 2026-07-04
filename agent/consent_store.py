import threading

_lock = threading.Lock()

# {session_id: {"tables": [...], "output_format": "docx"}}
# Production'da bu dict Redis veya bir veritabanıyla değiştirilir.
_pending: dict[str, dict] = {}


def store_pending(session_id: str, tables: list[str], output_format: str) -> None:
    with _lock:
        _pending[session_id] = {"tables": tables, "output_format": output_format}


def get_pending(session_id: str) -> dict | None:
    with _lock:
        return _pending.get(session_id)


def clear_pending(session_id: str) -> None:
    with _lock:
        _pending.pop(session_id, None)
