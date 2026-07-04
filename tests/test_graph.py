"""
Graph uçtan uca testi — gerçek Oracle + OpenAI bağlantısı gerektirir.

Çalıştırma:
    pytest -m integration tests/test_graph.py

Not: .env dosyasında DB_* ve OPENAI_API_KEY tanımlı olmalı.
"""

import pytest
from agent.graph import build_graph


@pytest.mark.integration
def test_graph():
    print("=" * 55)
    print("DW-DocAgent — Graph Uçtan Uca Test")
    print("=" * 55)

    graph = build_graph()

    # Test mesajı — intent_parser FACT_SALES'i çıkarmalı
    initial_state = {
        "message": "FACT_SALES tablosunu belgele",
        "tables": [],
        "output_format": "docx",
        "schemas": {},
        "lineage": {},
        "draft_docs": {},
        "quality_scores": {},
        "final_markdown": "",
        "approved": False,
        "retry_count": 0,
    }

    print(f"\nMesaj: '{initial_state['message']}'")
    print("-" * 55)

    result = graph.invoke(initial_state)

    print("\n" + "=" * 55)
    print("SONUÇ")
    print("=" * 55)
    print(f"Tablolar       : {result['tables']}")
    print(f"Format         : {result['output_format']}")
    print(f"Schema sayısı  : {len(result['schemas'])}")
    print(f"Döküman sayısı : {len(result['draft_docs'])}")
    print(f"Kalite skorları: {result['quality_scores']}")
    print(f"Onaylandı      : {result['approved']}")
    print(f"Retry sayısı   : {result['retry_count']}")
    print(f"Final markdown : {len(result['final_markdown'])} karakter")

    if result["final_markdown"]:
        print("\n--- Üretilen Döküman (ilk 500 karakter) ---")
        print(result["final_markdown"][:500])
        print("...")

    assert result["tables"] == ["FACT_SALES"], "Tablo adı çıkarılamadı"
    assert result["schemas"].get("FACT_SALES"), "Schema boş"
    assert result["draft_docs"].get("FACT_SALES"), "Döküman üretilemedi"
    assert result["final_markdown"], "Final markdown boş"

    print("\n✓ Graph testi geçti.\n")


if __name__ == "__main__":
    try:
        test_graph()
    except Exception as e:
        print(f"\n✗ Hata: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)