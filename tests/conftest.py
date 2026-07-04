"""
pytest koleksiyon konfigürasyonu.

Oracle veritabanı gerektiren test scriptleri pytest tarafından otomatik toplanmaz.
Bu scriptler manuel olarak çalıştırılabilir:
    python tests/test_oracle_client.py
    python tests/test_server.py
    python tests/test_graph.py
    python tests/test_output.py
"""

collect_ignore = [
    "test_oracle_client.py",
    "test_graph.py",
    "test_server.py",
    "test_output.py",
    "create_test_schema.py",
]
