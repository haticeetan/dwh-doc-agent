"""
Output katmanı testi — graph çalıştırıp docx ve pdf üretir.
Gerçek Oracle + OpenAI bağlantısı gerektirir.

Çalıştırma:
    pytest -m integration tests/test_output.py
"""

import os
import pytest
from agent.graph import build_graph
from output.file_server import generate_document, get_file_path


@pytest.mark.integration
def test_output():
    print("=" * 55)
    print("DW-DocAgent — Output Katmanı Testi")
    print("=" * 55)

    graph = build_graph()

    for fmt in ["docx", "pdf"]:
        print(f"\n--- Format: {fmt.upper()} ---")

        result = graph.invoke({
            "message": "FACT_SALES tablosunu belgele",
            "tables": [],
            "output_format": fmt,
            "schemas": {}, "lineage": {}, "draft_docs": {},
            "quality_scores": {}, "final_markdown": "",
            "approved": False, "retry_count": 0,
        })

        assert result["final_markdown"], "final_markdown boş"
        print(f"  ✓ Graph tamamlandı ({len(result['final_markdown'])} karakter)")

        job_id = generate_document(
            final_markdown=result["final_markdown"],
            output_format=fmt,
            title="FACT_SALES"
        )
        print(f"  ✓ job_id: {job_id}")

        path = get_file_path(job_id)
        assert path and os.path.exists(path), "Dosya oluşturulamadı"
        size_kb = os.path.getsize(path) / 1024
        print(f"  ✓ Dosya: {os.path.basename(path)} ({size_kb:.1f} KB)")

    print("\n✓ Output testleri geçti.\n")
