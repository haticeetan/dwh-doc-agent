"""
Oracle bağlantı testi — oracle_mcp/oracle_client.py'yi doğrular.
Gerçek Oracle bağlantısı gerektirir.

Çalıştırma:
    pytest -m integration tests/test_oracle_client.py
"""

import pytest
from oracle_mcp.oracle_client import get_pool, get_connection, execute_query, close_pool
import config


@pytest.mark.integration
def test_thick_mode_ve_pool():
    print("\n--- Test 1: Thick Mode ve Pool ---")
    pool = get_pool()
    assert pool is not None
    print(f"  ✓ Pool oluşturuldu (min={config.POOL_MIN}, max={config.POOL_MAX})")


@pytest.mark.integration
def test_baglanti():
    print("\n--- Test 2: Bağlantı ---")
    with get_connection() as conn:
        assert conn is not None
        print("  ✓ Bağlantı alındı ve pool'a geri bırakıldı")


@pytest.mark.integration
def test_oracle_version():
    print("\n--- Test 3: Basit sorgu (Oracle versiyonu) ---")
    rows = execute_query("SELECT * FROM v$version WHERE banner LIKE 'Oracle%'")
    assert len(rows) > 0
    print(f"  ✓ Oracle sürümü: {rows[0]['banner']}")


@pytest.mark.integration
def test_execute_query_parametreli():
    print("\n--- Test 4: Parametreli sorgu (ALL_TABLES) ---")
    rows = execute_query(
        """
        SELECT table_name, num_rows
        FROM all_tables
        WHERE owner = :owner
        AND ROWNUM <= 3
        """,
        {"owner": config.DB_USER.upper()}
    )
    print(f"  ✓ {len(rows)} tablo bulundu")
    for row in rows:
        print(f"    - {row['table_name']} ({row['num_rows']} satır)")


@pytest.mark.integration
def test_pool_kapat():
    print("\n--- Test 5: Pool kapatma ---")
    close_pool()
    print("  ✓ Pool kapatıldı")
