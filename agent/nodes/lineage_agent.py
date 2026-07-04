from agent.state import DocAgentState
from logger import get_logger

logger = get_logger(__name__)


def build_lineage_graph(table: str, deps: dict) -> dict:
    """
    dep_tracer çıktısını düzenli bir lineage objesine dönüştürür.
    doc_writer'ın kullanacağı formata getirir.
    """
    return {
        "table": table,
        "depends_on": [
            {
                "table": fk["r_table_name"],
                "via_column": fk["column_name"],
                "ref_column": fk["r_column_name"],
                "confirmed": True,
            }
            for fk in deps.get("foreign_keys", [])
        ],
        "referenced_by": [
            {
                "table": ref["table_name"],
                "via_column": ref["column_name"],
                "confirmed": True,
            }
            for ref in deps.get("referenced_by", [])
        ],
        "implicit_relations": [
            {
                "table": rel["possible_ref_table"],
                "via_column": rel["column_name"],
                "confidence": rel["confidence"],
                "confirmed": False,
            }
            for rel in deps.get("implicit_relations", [])
        ],
        "used_by_objects": deps.get("used_by_objects", []),
    }


def lineage_agent_node(state: DocAgentState) -> DocAgentState:
    """
    dep_tracer çıktısını alıp düzenli lineage grafına dönüştürür.
    schema_analyst'ın doldurduğu lineage verisini zenginleştirir.

    Girdi : state["lineage"] (dep_tracer ham çıktısı)
    Çıktı : state["lineage"] (düzenlenmiş lineage grafı)
    """
    tables = state.get("tables", [])
    raw_lineage = state.get("lineage", {})
    enriched_lineage = {}

    for table in tables:
        deps = raw_lineage.get(table, {})

        if not deps:
            logger.warning(f"{table} için bağımlılık verisi yok, atlanıyor")
            enriched_lineage[table] = build_lineage_graph(table, {})
            continue

        graph = build_lineage_graph(table, deps)
        enriched_lineage[table] = graph

        confirmed = len(graph["depends_on"]) + len(graph["referenced_by"])
        implicit = len(graph["implicit_relations"])
        obj_count = len(graph["used_by_objects"])

        logger.info(
            f"{table}: {confirmed} doğrulanmış ilişki, "
            f"{implicit} örtük ilişki, {obj_count} kullanan nesne"
        )

    return {
        **state,
        "lineage": enriched_lineage,
    }