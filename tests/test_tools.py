"""
Unit tests for MCP tool security and validation logic.
No Oracle connection required — tests pure helper behaviour.
"""
import re
import pytest


# ── table_search sanitisation ──────────────────────────────────────────────────

def _sanitise_keywords(keywords: list[str]) -> list[str]:
    """Mirrors the sanitisation in oracle_mcp/server.py table_search."""
    clean = [re.sub(r"['\";\\]", "", kw).upper().strip() for kw in keywords]
    return [kw for kw in clean if kw]


class TestTableSearchSanitisation:
    def test_normal_keyword_uppercased(self):
        assert _sanitise_keywords(["sales"]) == ["SALES"]

    def test_quote_stripped(self):
        result = _sanitise_keywords(["O'RDERS"])
        assert "'" not in result[0]

    def test_semicolon_stripped(self):
        result = _sanitise_keywords(["ORDERS;"])
        assert ";" not in result[0]

    def test_empty_keyword_removed(self):
        result = _sanitise_keywords(["", "  "])
        assert result == []

    def test_multiple_keywords(self):
        result = _sanitise_keywords(["sales", "orders"])
        assert "SALES" in result
        assert "ORDERS" in result
