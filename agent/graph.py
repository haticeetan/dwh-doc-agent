from langgraph.graph import StateGraph, END

from agent.state import DocAgentState
from agent.nodes.intent_parser import intent_parser_node
from agent.nodes.consent_gate import consent_gate_node
from agent.nodes.table_discovery import table_discovery_node
from agent.nodes.table_info import table_info_node
from agent.nodes.schema_analyst import schema_analyst_node
from agent.nodes.lineage_agent import lineage_agent_node
from agent.nodes.doc_writer import doc_writer_node
from agent.nodes.quality_checker import quality_checker_node
from logger import get_logger
from tracer import trace_node
import config

logger = get_logger(__name__)


def route_after_consent(state: DocAgentState) -> str:
    """
    consent_gate sonrası nereye gidileceğine karar verir.

    waiting_consent=True → END   (kullanıcıdan onay bekleniyor)
    chitchat             → END   (yanıt zaten chitchat_response'da)
    discovery            → table_discovery
    document             → schema_analyst (onay alındı, belgeleme başlıyor)
    """
    if state.get("waiting_consent"):
        return END
    intent_type = state.get("intent_type", "document")
    if intent_type == "chitchat":
        return END
    if intent_type == "discovery":
        return "table_discovery"
    if intent_type == "table_info":
        return "table_info"
    return "schema_analyst"


def route_after_quality(state: DocAgentState) -> str:
    """
    quality_checker sonrası nereye gidileceğine karar verir.

    Kurallar:
        - Tüm tablolar 0.7 üstü puan aldıysa → END (output katmanı devralır)
        - Herhangi biri 0.7 altındaysa ve retry < MAX_RETRY → doc_writer (yeniden yaz)
        - retry >= MAX_RETRY → END (düşük skorla da geç, logla)
    """
    scores = state.get("quality_scores", {})
    retry_count = state.get("retry_count", 0)

    low_score_tables = [t for t, s in scores.items() if s < 0.7]

    if not low_score_tables:
        return END

    if retry_count >= config.MAX_RETRY:
        logger.warning(
            f"MAX_RETRY ({config.MAX_RETRY}) aşıldı. "
            f"Düşük skorlu tablolar: {low_score_tables}. Düşük skorla output'a geçiliyor."
        )
        return END

    return "doc_writer"


def build_graph() -> any:
    """
    LangGraph graph'ını oluşturur ve derler.

    Akış:
        intent_parser → schema_analyst → lineage_agent → doc_writer → quality_checker
                                              ↑               │
                                              └── skor < 0.7 ─┘
                                                  retry < MAX
    """
    graph = StateGraph(DocAgentState)

    # ── Node'ları ekle (her biri trace_node ile span'a sarılıyor) ────────────
    graph.add_node("intent_parser",   trace_node("intent_parser")(intent_parser_node))
    graph.add_node("consent_gate",    trace_node("consent_gate")(consent_gate_node))
    graph.add_node("table_discovery", trace_node("table_discovery")(table_discovery_node))
    graph.add_node("table_info",      trace_node("table_info")(table_info_node))
    graph.add_node("schema_analyst",  trace_node("schema_analyst")(schema_analyst_node))
    graph.add_node("lineage_agent",   trace_node("lineage_agent")(lineage_agent_node))
    graph.add_node("doc_writer",      trace_node("doc_writer")(doc_writer_node))
    graph.add_node("quality_checker", trace_node("quality_checker")(quality_checker_node))

    # ── Başlangıç noktası ─────────────────────────────────────────────────────
    graph.set_entry_point("intent_parser")

    # ── intent_parser → consent_gate (her zaman) ──────────────────────────────
    graph.add_edge("intent_parser", "consent_gate")

    # ── Koşullu edge: consent_gate sonrası ────────────────────────────────────
    graph.add_conditional_edges(
        "consent_gate",
        route_after_consent,
        {
            "table_discovery": "table_discovery",
            "table_info":      "table_info",
            "schema_analyst":  "schema_analyst",
            END: END,
        }
    )

    # ── Discovery ve table_info akışları ─────────────────────────────────────
    graph.add_edge("table_discovery", END)
    graph.add_edge("table_info",      END)

    # ── Document akışı ────────────────────────────────────────────────────────
    graph.add_edge("schema_analyst", "lineage_agent")
    graph.add_edge("lineage_agent",  "doc_writer")
    graph.add_edge("doc_writer",     "quality_checker")

    # ── Koşullu edge: quality_checker sonrası ─────────────────────────────────
    graph.add_conditional_edges(
        "quality_checker",
        route_after_quality,
        {
            "doc_writer": "doc_writer",
            END: END,
        }
    )

    return graph.compile()