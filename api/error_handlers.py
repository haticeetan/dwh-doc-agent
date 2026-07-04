from fastapi import Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse

from api.exceptions import (
    AIServiceError,
    DatabaseUnavailableError,
    DocAgentError,
    DocumentGenerationError,
    DocumentNotFoundError,
)
from api.schemas import ProblemDetail
from logger import get_logger, correlation_id
from resilience import CircuitOpenError

logger = get_logger(__name__)

_PROBLEM_CONTENT_TYPE = "application/problem+json"


# ── Yardımcı fonksiyonlar ─────────────────────────────────────────────────────

def _build_response(problem: ProblemDetail) -> JSONResponse:
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(exclude_none=True),
        headers={"Content-Type": _PROBLEM_CONTENT_TYPE},
    )


def _instance(request: Request) -> str:
    return str(request.url.path)


def _corr_id() -> str:
    return correlation_id.get("-")


def _status_title(status: int) -> str:
    return {
        400: "Geçersiz istek",
        401: "Kimlik doğrulama gerekli",
        403: "Erişim reddedildi",
        404: "Bulunamadı",
        405: "Metod desteklenmiyor",
        422: "İşlenemeyen içerik",
        429: "Çok fazla istek",
        500: "Sunucu hatası",
        503: "Servis kullanılamıyor",
    }.get(status, "Hata")


# ── Uygulama hata handler'ları ────────────────────────────────────────────────

async def handle_document_not_found(request: Request, exc: DocumentNotFoundError) -> JSONResponse:
    logger.warning(f"Belge bulunamadı | path={_instance(request)}")
    return _build_response(ProblemDetail(
        type="urn:dw-docagent:error:document-not-found",
        title="Belge bulunamadı",
        status=404,
        detail=(
            "İstenen belge bulunamadı veya geçerlilik süresi doldu. "
            "Yeni bir döküman oluşturabilirsiniz."
        ),
        instance=_instance(request),
        correlation_id=_corr_id(),
    ))


async def handle_database_unavailable(
    request: Request, exc: DatabaseUnavailableError
) -> JSONResponse:
    # Tam hata (DSN, host gibi iç detaylar dahil) yalnızca log'a yazılır
    logger.error("Veritabanı erişim hatası", exc_info=True)
    return _build_response(ProblemDetail(
        type="urn:dw-docagent:error:database-unavailable",
        title="Veritabanı kullanılamıyor",
        status=503,
        detail=(
            "Veri ambarına şu an ulaşılamıyor. "
            "Lütfen birkaç dakika sonra tekrar deneyin."
        ),
        instance=_instance(request),
        correlation_id=_corr_id(),
    ))


async def handle_ai_service_error(request: Request, exc: AIServiceError) -> JSONResponse:
    logger.error("AI servis hatası", exc_info=True)
    return _build_response(ProblemDetail(
        type="urn:dw-docagent:error:ai-service-unavailable",
        title="AI servisi kullanılamıyor",
        status=503,
        detail=(
            "Döküman oluşturma servisi şu an yanıt vermiyor. "
            "Lütfen birkaç dakika sonra tekrar deneyin."
        ),
        instance=_instance(request),
        correlation_id=_corr_id(),
    ))


async def handle_document_generation_error(
    request: Request, exc: DocumentGenerationError
) -> JSONResponse:
    logger.error("Döküman üretim hatası", exc_info=True)
    return _build_response(ProblemDetail(
        type="urn:dw-docagent:error:document-generation-failed",
        title="Döküman üretilemedi",
        status=500,
        detail=(
            "Belge oluşturma sırasında bir sorun oluştu. "
            "Lütfen tekrar deneyin."
        ),
        instance=_instance(request),
        correlation_id=_corr_id(),
    ))


# ── Altyapı hata handler'ları ─────────────────────────────────────────────────

async def handle_circuit_open(request: Request, exc: CircuitOpenError) -> JSONResponse:
    # CircuitOpenError mesajı kaç saniye kaldığını söyler — bu log'a yazılır, kullanıcıya değil
    logger.warning(f"Circuit breaker açık: {exc}")
    return _build_response(ProblemDetail(
        type="urn:dw-docagent:error:service-circuit-open",
        title="Servis geçici olarak duraklatıldı",
        status=503,
        detail=(
            "Servis ardışık hatalar nedeniyle geçici olarak devre dışı. "
            "Lütfen 30 saniye sonra tekrar deneyin."
        ),
        instance=_instance(request),
        correlation_id=_corr_id(),
    ))


async def handle_oracle_error(request: Request, exc: Exception) -> JSONResponse:
    # Oracle hataları DSN, host, şema adı içerebilir — sadece log'a
    logger.error("Oracle DatabaseError (yakalanmamış)", exc_info=True)
    return _build_response(ProblemDetail(
        type="urn:dw-docagent:error:database-unavailable",
        title="Veritabanı hatası",
        status=503,
        detail=(
            "Veri ambarına erişimde bir sorun oluştu. "
            "Lütfen tekrar deneyin."
        ),
        instance=_instance(request),
        correlation_id=_corr_id(),
    ))


async def handle_openai_error(request: Request, exc: Exception) -> JSONResponse:
    # OpenAI hataları API endpoint, token sayısı gibi detaylar içerebilir — sadece log'a
    logger.error("OpenAI API hatası (yakalanmamış)", exc_info=True)
    return _build_response(ProblemDetail(
        type="urn:dw-docagent:error:ai-service-unavailable",
        title="AI servisi hatası",
        status=503,
        detail=(
            "AI servisiyle iletişimde sorun yaşandı. "
            "Lütfen tekrar deneyin."
        ),
        instance=_instance(request),
        correlation_id=_corr_id(),
    ))


# ── FastAPI yerleşik hata handler'ları ────────────────────────────────────────

async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    """Mevcut HTTPException'ları RFC 7807 formatına dönüştürür."""
    logger.warning(f"HTTP {exc.status_code} | path={_instance(request)} | {exc.detail}")
    return _build_response(ProblemDetail(
        type=f"urn:dw-docagent:error:http-{exc.status_code}",
        title=_status_title(exc.status_code),
        status=exc.status_code,
        detail=exc.detail if isinstance(exc.detail, str) else "Bir hata oluştu.",
        instance=_instance(request),
        correlation_id=_corr_id(),
    ))


async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Pydantic doğrulama hatalarını RFC 7807 formatına dönüştürür."""
    errors = exc.errors()
    detail = "; ".join(
        f"{' > '.join(str(loc) for loc in e['loc'])}: {e['msg']}"
        for e in errors
    )
    logger.warning(f"Doğrulama hatası | {detail}")
    return _build_response(ProblemDetail(
        type="urn:dw-docagent:error:validation-error",
        title="Geçersiz istek",
        status=422,
        detail=detail,
        instance=_instance(request),
        correlation_id=_corr_id(),
    ))


async def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """
    Son ağ: hiçbir handler tarafından yakalanmayan tüm hatalar buraya düşer.
    Stack trace ve hata mesajı asla kullanıcıya gösterilmez — yalnızca log'a yazılır.
    """
    logger.error(
        f"Beklenmedik hata | path={_instance(request)} | type={type(exc).__name__}",
        exc_info=True,
    )
    return _build_response(ProblemDetail(
        type="urn:dw-docagent:error:internal-error",
        title="Beklenmedik hata",
        status=500,
        detail=(
            "Sunucu tarafında beklenmedik bir hata oluştu. "
            "Sorun devam ederse destek ekibiyle iletişime geçin."
        ),
        instance=_instance(request),
        correlation_id=_corr_id(),
    ))
