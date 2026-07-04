import logging
from contextlib import contextmanager
from typing import Any

import oracledb
from opentelemetry import trace as otel_trace

from oracle_mcp import config
from resilience import oracle_circuit, oracle_retry, CircuitOpenError

logger = logging.getLogger(__name__)
_tracer = otel_trace.get_tracer(__name__)

# Modül yüklenirken Thick Mode başlatılır — sadece bir kez çağrılmalı
_thick_mode_initialized = False
_pool: oracledb.ConnectionPool | None = None


def _init_thick_mode() -> None:
    """
    Oracle Instant Client ile Thick Mode'u başlatır.
    Bu fonksiyon modül ilk import edildiğinde bir kez çalışır.
    """
    global _thick_mode_initialized
    if _thick_mode_initialized:
        return

    try:
        oracledb.init_oracle_client(lib_dir=config.ORACLE_CLIENT_LIB)
        _thick_mode_initialized = True
        logger.info(f"Oracle Thick Mode başlatıldı: {config.ORACLE_CLIENT_LIB}")
    except oracledb.DatabaseError as e:
        logger.error(
            f"Thick Mode başlatılamadı. Instant Client dizinini kontrol et: "
            f"{config.ORACLE_CLIENT_LIB}\nHata: {e}"
        )
        raise


def get_pool() -> oracledb.ConnectionPool:
    """
    Bağlantı pool'unu oluşturur veya mevcut pool'u döner.
    Uygulama yaşam döngüsü boyunca tek bir pool kullanılır.
    """
    global _pool
    if _pool is not None:
        return _pool

    _init_thick_mode()

    try:
        _pool = oracledb.create_pool(
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            dsn=config.DB_DSN,
            min=config.POOL_MIN,
            max=config.POOL_MAX,
            increment=config.POOL_INCREMENT,
        )
        logger.info(
            f"Bağlantı pool oluşturuldu — "
            f"DSN: {config.DB_DSN} | "
            f"min={config.POOL_MIN} max={config.POOL_MAX}"
        )
        return _pool
    except oracledb.DatabaseError as e:
        logger.error(f"Pool oluşturulamadı: {e}")
        raise


@contextmanager
def get_connection():
    """
    Pool'dan bir bağlantı alır, işlem bitince otomatik geri bırakır.

    Kullanım:
        with get_connection() as conn:
            cursor = conn.cursor()
            ...
    """
    pool = get_pool()
    conn = pool.acquire()
    try:
        yield conn
    except oracledb.DatabaseError as e:
        logger.error(f"Veritabanı hatası: {e}")
        raise
    finally:
        pool.release(conn)


def execute_query(sql: str, params: dict | None = None) -> list[dict[str, Any]]:
    """
    Parameterized sorgu çalıştırır, sonuçları dict listesi olarak döner.

    Args:
        sql:    Çalıştırılacak SQL — parametre için :param_adi formatı kullan
        params: Parametre dict — örnek: {"table_name": "ORDERS"}

    Returns:
        Her satırın kolon_adi: deger şeklinde dict olduğu liste

    Örnek:
        rows = execute_query(
            "SELECT column_name FROM all_tab_columns WHERE table_name = :tname",
            {"tname": "ORDERS"}
        )
    """
    params = params or {}

    with _tracer.start_as_current_span("oracle.execute_query") as span:
        span.set_attribute("db.system", "oracle")
        span.set_attribute("db.statement", sql.strip()[:200])

        # Closure: bağlantı alıp sorguyu çalıştırır.
        # oracle_retry ile sarılarak geçici hatalarda yeniden denenir,
        # oracle_circuit üzerinden çağrılarak ardışık hata eşiğinde devre açılır.
        def _run():
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, params)
                    columns = [col[0].lower() for col in cursor.description]
                    return [dict(zip(columns, row)) for row in cursor.fetchall()]

        try:
            rows = oracle_circuit.call(oracle_retry(_run))
        except CircuitOpenError as e:
            logger.error(str(e))
            raise
        except oracledb.DatabaseError as e:
            span.record_exception(e)
            raise

        span.set_attribute("db.row_count", len(rows))

    logger.debug(f"Sorgu {len(rows)} satır döndü | SQL: {sql[:80]}...")
    return rows


def close_pool() -> None:
    """
    Uygulama kapanırken pool'u düzgünce kapatır.
    FastAPI lifespan event'ında çağrılmalı.
    """
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
        logger.info("Bağlantı pool kapatıldı.")