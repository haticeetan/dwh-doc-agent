from openai import OpenAI
from agent.state import DocAgentState
from logger import get_logger
from resilience import openai_retry
from oracle_mcp.server import table_lister

logger = get_logger(__name__)
_client: OpenAI | None = None

# Oracle sistem/dahili tablo tanımlayıcıları
_SYSTEM_PREFIXES = (
    "SDO_", "OGIS_", "ODCI_", "RDF_", "NTV2_", "ALL_UNIFIED_",
    "AW$", "DR$", "KU$", "OL$", "MODELGTT", "XDB_", "SPD_", "SRS",
)
_SYSTEM_EXACT = {
    "DUAL", "AV_DUAL", "HELP", "AUDIT_ACTIONS",
    "SCHEDULER_FILEWATCHER_QT", "IMPDP_STATS", "SAM_SPARSITY_ADVICE",
    "STMT_AUDIT_OPTION_MAP", "SYSTEM_PRIVILEGE_MAP",
    "TABLE_PRIVILEGE_MAP", "USER_PRIVILEGE_MAP",
}


def _is_system_table(table_name: str) -> bool:
    if "$" in table_name:
        return True
    if table_name in _SYSTEM_EXACT:
        return True
    return any(table_name.startswith(p) for p in _SYSTEM_PREFIXES)


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def table_discovery_node(state: DocAgentState) -> DocAgentState:
    """
    Veritabanı keşfi node'u. discovery intent'i için çalışır.
    Veritabanındaki TÜM tabloları çeker, Oracle sistem tablolarını filtreler,
    hangilerinin kullanıcının sorusuyla ilgili olduğuna LLM karar verir.

    Girdi : state["message"]
    Çıktı : state["discovery_result"], state["final_markdown"]
    """
    message = state.get("message", "")

    raw_tables = table_lister()
    user_tables = [t for t in raw_tables if not _is_system_table(t["table_name"])]
    system_count = len(raw_tables) - len(user_tables)

    logger.info(
        f"{len(raw_tables)} tablo bulundu — {len(user_tables)} kullanıcı, "
        f"{system_count} sistem tablosu filtrelendi"
    )

    if not user_tables:
        result = "Veri ambarında kullanıcı tablosu bulunamadı."
    else:
        result = _explain_with_llm(message, user_tables)

    return {
        **state,
        "discovery_result": result,
        "final_markdown": result,
    }


@openai_retry
def _explain_with_llm(user_message: str, user_tables: list[dict]) -> str:
    table_lines = "\n".join(
        f"- {row['table_name']}: {row.get('comments') or '(açıklama yok)'}"
        for row in user_tables
    )

    prompt = f"""Sen bir veri ambarı asistanısın. Kullanıcının sorusunu doğrudan ve kısa yanıtla.

Kullanıcı sorusu: {user_message}

Veritabanındaki kullanıcı tabloları ({len(user_tables)} adet):
{table_lines}

Yanıtlama kuralları:
- Tablo listelerini HER ZAMAN madde madde yaz: her tablo için `- **TABLO_ADI** — kısa açıklama` formatını kullan.
- Tablo sayısı sorulmuşsa önce `Veritabanında X kullanıcı tablosu bulunmaktadır.` yaz, ardından tabloları gruplara bölerek madde madde listele.
- FCT_ fact tablo, DIM_ boyut tablo, STAG_ staging gibi isimlendirme kalıplarından gruplar oluştur.
- Her madde tek satır olsun, gereksiz uzun açıklama yazma.
- "Açıklama:", "Özet:", "Öneri:" gibi bölüm başlıkları kullanma.
- Hiçbir tablo ilgili değilse dürüstçe belirt, tahmin uydurma.
- Kendi düşünce sürecini açıklama — sadece cevabı ver."""

    response = _get_client().chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
    )

    return response.choices[0].message.content
