"""
Unit tests for agent node helper functions.
No Oracle connection or OpenAI API calls required.
"""
import pytest
from agent.nodes.intent_parser import _extract_tables, _regex_fallback, IntentType
from agent.nodes.doc_writer import _strip_dwh_prefix, _col_matches_table, _build_relations_section


# ── intent_parser ──────────────────────────────────────────────────────────────

class TestExtractTables:
    def test_uppercase_table_name(self):
        assert "FACT_SALES" in _extract_tables("FACT_SALES tablosunu belgele")

    def test_quoted_table_name(self):
        assert "ORDERS" in _extract_tables('"ORDERS" tablosunu belgele')

    def test_multiple_tables(self):
        tables = _extract_tables("FACT_SALES ve DIM_CUSTOMER tablolarını belgele")
        assert "FACT_SALES" in tables
        assert "DIM_CUSTOMER" in tables

    def test_stopwords_excluded(self):
        tables = _extract_tables("PDF formatında belgele")
        assert "PDF" not in tables
        assert "BELGELE" not in tables

    def test_empty_message(self):
        assert _extract_tables("") == []


class TestRegexFallback:
    def test_table_found_returns_document(self):
        result = _regex_fallback("ORDERS tablosunu belgele")
        assert result.intent_type == IntentType.DOCUMENT
        assert "ORDERS" in result.tables

    def test_no_table_returns_chitchat(self):
        result = _regex_fallback("Merhaba nasılsın?")
        assert result.intent_type == IntentType.CHITCHAT
        assert result.tables == []

    def test_pdf_keyword_sets_format(self):
        result = _regex_fallback("ORDERS tablosunu PDF olarak belgele")
        assert result.output_format == "pdf"

    def test_default_format_is_docx(self):
        result = _regex_fallback("ORDERS tablosunu belgele")
        assert result.output_format == "docx"


# ── doc_writer ─────────────────────────────────────────────────────────────────

class TestStripDwhPrefix:
    def test_dim_prefix(self):
        assert _strip_dwh_prefix("DIM_CUSTOMER") == "CUSTOMER"

    def test_fact_prefix(self):
        assert _strip_dwh_prefix("FACT_SALES") == "SALES"

    def test_fct_prefix(self):
        assert _strip_dwh_prefix("FCT_ORDERS") == "ORDERS"

    def test_stag_prefix(self):
        assert _strip_dwh_prefix("STAG_PRODUCT") == "PRODUCT"

    def test_no_prefix(self):
        assert _strip_dwh_prefix("ORDERS") == "ORDERS"

    def test_unknown_prefix_unchanged(self):
        assert _strip_dwh_prefix("SRC_ORDERS") == "SRC_ORDERS"

    def test_compound_name_after_prefix(self):
        assert _strip_dwh_prefix("DIM_PRODUCT_CATEGORY") == "PRODUCT_CATEGORY"


class TestColMatchesTable:
    def test_exact_match(self):
        assert _col_matches_table("CUSTOMER", "CUSTOMER") is True

    def test_dwh_prefix_stripped_match(self):
        assert _col_matches_table("CUSTOMER", "DIM_CUSTOMER") is True

    def test_no_match(self):
        assert _col_matches_table("PRODUCT", "DIM_CUSTOMER") is False

    def test_sales_vs_fact_sales(self):
        assert _col_matches_table("SALES", "FACT_SALES") is True


class TestBuildRelationsSection:
    def test_single_table_returns_empty(self):
        result = _build_relations_section(
            table="FACT_SALES",
            deps={},
            schema={"columns": []},
            all_tables=["FACT_SALES"],
        )
        assert result == ""

    def test_multi_table_no_relations_returns_empty(self):
        result = _build_relations_section(
            table="FACT_SALES",
            deps={"depends_on": [], "referenced_by": [], "foreign_keys": [], "implicit_relations": []},
            schema={"columns": []},
            all_tables=["FACT_SALES", "DIM_CUSTOMER"],
        )
        assert result == ""

    def test_id_column_detected_as_relation(self):
        result = _build_relations_section(
            table="FACT_SALES",
            deps={"depends_on": [], "referenced_by": [], "foreign_keys": [], "implicit_relations": []},
            schema={
                "columns": [
                    {"column_name": "CUSTOMER_ID", "data_type": "NUMBER", "nullable": "Y", "comments": None}
                ]
            },
            all_tables=["FACT_SALES", "DIM_CUSTOMER"],
        )
        # CUSTOMER_ID → base=CUSTOMER → matches DIM_CUSTOMER via prefix stripping
        assert "DIM_CUSTOMER" in result
