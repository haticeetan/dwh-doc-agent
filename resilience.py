import logging
import threading
import time
from enum import Enum

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from logger import get_logger

logger = get_logger(__name__)


# ── OpenAI Retry ──────────────────────────────────────────────────────────────

def openai_retry(fn):
    """
    OpenAI API çağrısı başarısız olursa exponential backoff ile yeniden dener.

    Yeniden denenen (geçici) hatalar:
        RateLimitError      — API kotası doldu, biraz bekleyince geçer
        APITimeoutError     — istek zaman aşımına uğradı
        APIConnectionError  — ağ bağlantı problemi
        InternalServerError — OpenAI tarafı geçici hata (5xx)

    Yeniden denenmeyen (kalıcı) hatalar:
        AuthenticationError — geçersiz API anahtarı, tekrar denemek işe yaramaz
        BadRequestError     — hatalı prompt/parametre, tekrar denemek işe yaramaz

    Bekleme: 2s → 4s → 8s → 16s (üstel, max 60s), toplam 4 deneme.
    """
    from openai import (
        APIConnectionError,
        APITimeoutError,
        InternalServerError,
        RateLimitError,
    )

    return retry(
        retry=retry_if_exception_type(
            (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError)
        ),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(4),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )(fn)


# ── Oracle Retry ──────────────────────────────────────────────────────────────

def oracle_retry(fn):
    """
    Oracle DatabaseError durumunda exponential backoff ile yeniden dener.
    Bağlantı kopması, pool tükenmesi gibi geçici sorunlar için tasarlandı.

    Bekleme: 1s → 2s → 4s, toplam 3 deneme.
    """
    import oracledb

    return retry(
        retry=retry_if_exception_type(oracledb.DatabaseError),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )(fn)


# ── Circuit Breaker ───────────────────────────────────────────────────────────

class _CBState(Enum):
    CLOSED    = "closed"     # Normal çalışma
    OPEN      = "open"       # Devre açık — çağrılar reddedilir
    HALF_OPEN = "half_open"  # Test modu — tek çağrıya izin verilir


class CircuitBreaker:
    """
    Üç durumlu circuit breaker implementasyonu.

    Durum geçişleri:
        CLOSED → OPEN      : failure_threshold kadar ardışık hata oluşunca
        OPEN   → HALF_OPEN : recovery_timeout saniye geçince
        HALF_OPEN → CLOSED : test çağrısı başarılı olunca
        HALF_OPEN → OPEN   : test çağrısı da başarısız olunca

    Thread-safe: tüm durum değişiklikleri Lock ile korunur.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state = _CBState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        return self._state.value

    def call(self, fn, *args, **kwargs):
        """
        fn'i circuit breaker mantığıyla çağırır.
        Devre açıksa CircuitOpenError fırlatır.
        """
        with self._lock:
            self._maybe_half_open()
            if self._state == _CBState.OPEN:
                remaining = self.recovery_timeout - (
                    time.monotonic() - self._last_failure_time
                )
                raise CircuitOpenError(
                    f"[{self.name}] Devre açık — "
                    f"{max(0, remaining):.0f}s sonra tekrar denenecek"
                )

        try:
            result = fn(*args, **kwargs)
            self._on_success()
            return result
        except CircuitOpenError:
            raise
        except Exception:
            self._on_failure()
            raise

    def _maybe_half_open(self) -> None:
        if (
            self._state == _CBState.OPEN
            and time.monotonic() - self._last_failure_time >= self.recovery_timeout
        ):
            self._state = _CBState.HALF_OPEN
            logger.info(f"[{self.name}] Circuit HALF_OPEN — test çağrısına izin veriliyor")

    def _on_success(self) -> None:
        with self._lock:
            if self._state == _CBState.HALF_OPEN:
                logger.info(f"[{self.name}] Circuit CLOSED — servis toparlıydı")
            self._state = _CBState.CLOSED
            self._failure_count = 0

    def _on_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if (
                self._state == _CBState.HALF_OPEN
                or self._failure_count >= self.failure_threshold
            ):
                self._state = _CBState.OPEN
                logger.error(
                    f"[{self.name}] Circuit OPEN — "
                    f"{self._failure_count} ardışık hata, "
                    f"{self.recovery_timeout:.0f}s bekleniyor"
                )
            else:
                logger.warning(
                    f"[{self.name}] Hata {self._failure_count}/{self.failure_threshold}"
                )


class CircuitOpenError(Exception):
    """Circuit breaker OPEN durumdayken çağrı yapılmaya çalışıldığında fırlatılır."""
    pass


# ── Paylaşılan örnekler ───────────────────────────────────────────────────────
# Modül import edildiğinde bir kez oluşturulur; tüm thread'ler bu örneği paylaşır.

oracle_circuit = CircuitBreaker(
    name="oracle",
    failure_threshold=3,
    recovery_timeout=30.0,
)
