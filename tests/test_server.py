"""
MCP Tool testleri — oracle_mcp/server.py'yi doğrular.
Gerçek Oracle bağlantısı gerektirir.

Çalıştırma:
    pytest -m integration tests/test_server.py

Not: .env dosyasının dolu olduğundan emin ol.
     TEST_TABLE değişkenini kendi şemanızdaki gerçek bir tablo adıyla değiştir.
"""

import pytest
from oracle_mcp.server import schema_reader, dep_tracer, sample_fetcher

# ─── Buraya kendi tablolarından birini yaz ───
TEST_TABLE = "FACT_SALES"   # Oracle'da var olduğundan emin ol
# ────────────────────────────────────────────


@pytest.mark.integration
def test_schema_reader():
    print("\n--- Test 1: schema_reader ---")
    result = schema_reader(TEST_TABLE)

    assert "table_name" in result
    assert "columns" in result
    assert "constraints" in result

    print(f"  ✓ Tablo: {result['table_name']}")
    print(f"  ✓ Kolon sayısı: {len(result['columns'])}")
    for col in result["columns"][:3]:
        print(f"    - {col['column_name']} ({col['data_type']}) | comment: {col.get('comments')}")
    print(f"  ✓ Constraint sayısı: {len(result['constraints'])}")
    for c in result["constraints"]:
        ref = f" → {c['r_table_name']}" if c.get("r_table_name") else ""
        print(f"    - {c['constraint_type']} | {c['column_name']}{ref}")


@pytest.mark.integration
def test_dep_tracer():
    print("\n--- Test 2: dep_tracer ---")
    result = dep_tracer(TEST_TABLE)

    assert "foreign_keys" in result
    assert "referenced_by" in result
    assert "used_by_objects" in result
    assert "implicit_relations" in result

    print(f"  ✓ FK sayısı: {len(result['foreign_keys'])}")
    for fk in result["foreign_keys"]:
        print(f"    - {fk['column_name']} → {fk['r_table_name']}.{fk['r_column_name']}")

    print(f"  ✓ Bu tabloyu referans alan: {len(result['referenced_by'])} tablo")
    print(f"  ✓ Kullanan nesneler: {len(result['used_by_objects'])}")
    print(f"  ✓ Örtük ilişki tahmini: {len(result['implicit_relations'])}")


@pytest.mark.integration
def test_sample_fetcher():
    print("\n--- Test 3: sample_fetcher ---")
    result = sample_fetcher(TEST_TABLE, limit=3)

    assert "table_name" in result
    assert "sample_rows" in result

    print(f"  ✓ Tablo: {result['table_name']}")
    print(f"  ✓ Toplam satır (yaklaşık): {result['row_count']}")
    print(f"  ✓ Örnek satır sayısı: {len(result['sample_rows'])}")
    if result["sample_rows"]:
        print(f"  ✓ İlk satır kolonları: {list(result['sample_rows'][0].keys())}")
