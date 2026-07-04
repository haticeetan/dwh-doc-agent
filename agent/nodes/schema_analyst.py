from agent.state import DocAgentState
from logger import get_logger
from oracle_mcp.server import schema_reader, dep_tracer, sample_fetcher

logger = get_logger(__name__)


def schema_analyst_node(state: DocAgentState) -> DocAgentState:
    """
    Her tablo için Oracle'dan şema ve bağımlılık bilgisini çeker.
    Kullanıcı onay verdiyse (use_sample_data=True) örnek satırları da çeker.

    Girdi : state["tables"], state["use_sample_data"]
    Çıktı : state["schemas"], state["lineage"], state["sample_data"]
    """
    tables = state.get("tables", [])
    use_sample_data = state.get("use_sample_data", False)
    schemas = {}
    lineage = {}
    sample_data = {}

    for table in tables:
        logger.info(f"{table} analiz ediliyor")

        # Tablo yapısı
        schema = schema_reader(table)
        schemas[table] = schema

        if not schema["columns"]:
            logger.warning(f"{table} bulunamadı veya erişim yok")
            continue

        logger.debug(f"{table}: {len(schema['columns'])} kolon, {len(schema['constraints'])} constraint")

        # Örnek veri — yalnızca kullanıcı onay verdiyse
        if use_sample_data:
            result = sample_fetcher(table, limit=5)
            rows = result.get("sample_rows", [])
            sample_data[table] = rows
            logger.info(f"{table}: {len(rows)} örnek satır çekildi")

        # Bağımlılıklar
        deps = dep_tracer(table)
        lineage[table] = deps

        fk_count = len(deps["foreign_keys"])
        ref_count = len(deps["referenced_by"])
        implicit_count = len(deps["implicit_relations"])
        logger.debug(f"{table}: {fk_count} FK, {ref_count} referans, {implicit_count} örtük ilişki")

    found = [t for t in tables if schemas.get(t, {}).get("columns")]
    missing = [t for t in tables if t not in found]

    if missing and not found:
        missing_list = ", ".join(f"**{t}**" for t in missing)
        return {
            **state,
            "schemas": schemas,
            "lineage": lineage,
            "sample_data": sample_data,
            "intent_type": "chitchat",
            "chitchat_response": (
                f"{missing_list} tablosu veritabanında bulunamadı veya bu kullanıcıyla "
                "erişim izni yok. Tablo adını kontrol edip tekrar deneyin."
            ),
        }

    return {
        **state,
        "schemas": schemas,
        "lineage": lineage,
        "sample_data": sample_data,
    }