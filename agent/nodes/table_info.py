from openai import OpenAI
from agent.state import DocAgentState
from logger import get_logger
from resilience import openai_retry
from oracle_mcp.server import schema_reader
from oracle_mcp.oracle_client import execute_query

logger = get_logger(__name__)
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def table_info_node(state: DocAgentState) -> DocAgentState:
    """
    Belirli bir tablo hakkında bilgi sorusu geldiğinde çalışır.
    Tam dökümantasyon üretmek yerine schema'yı okuyup kısa bir özet verir.

    Girdi : state["tables"], state["message"]
    Çıktı : state["discovery_result"], state["final_markdown"]
    """
    tables = state.get("tables", [])
    message = state.get("message", "")

    if not tables:
        result = "Hangi tabloyu merak ettiğinizi belirtir misiniz? Örnek: 'DIM_PRODUCT tablosu ne içeriyor?'"
        return {**state, "discovery_result": result, "final_markdown": result}

    table_name = tables[0]
    schema = schema_reader(table_name)

    if not schema["columns"]:
        result = f"**{table_name}** tablosu bulunamadı veya erişim yetkiniz yok."
        return {**state, "discovery_result": result, "final_markdown": result}

    # Satır sayısı: Oracle istatistik tablosundan — hiçbir gerçek veri satırı çekilmiyor
    result_rows = execute_query(
        "SELECT num_rows FROM all_tables WHERE table_name = :tname",
        {"tname": table_name}
    )
    row_count = result_rows[0]["num_rows"] if result_rows else None

    logger.info(f"{table_name}: {len(schema['columns'])} kolon, ~{row_count} satır, bilgi özeti üretiliyor")
    result = _summarize_with_llm(message, table_name, schema, row_count)

    return {
        **state,
        "discovery_result": result,
        "final_markdown": result,
    }


@openai_retry
def _summarize_with_llm(user_message: str, table_name: str, schema: dict, row_count: int | None) -> str:
    column_lines = "\n".join(
        f"- {col['column_name']} ({col['data_type']})"
        + (f": {col['comments']}" if col.get("comments") else "")
        for col in schema["columns"]
    )

    row_count_line = (
        f"Yaklaşık satır sayısı: {row_count:,}" if row_count is not None
        else "Satır sayısı: istatistik mevcut değil (tablo hiç analiz edilmemiş olabilir)"
    )

    prompt = f"""Sen bir veri ambarı asistanısın. Kullanıcının sorusunu doğrudan ve kısa yanıtla.

Kullanıcı sorusu: {user_message}

{table_name} tablosu hakkında bilgiler:
- {row_count_line}

Kolonlar:
{column_lines}

Kurallar:
- Kullanıcı satır sayısı sorduysa önce onu belirt, sonra kısa bağlam ekle.
- Kullanıcı içerik sorduysa tablonun ne tuttuğunu 1-2 cümleyle açıkla, ardından önemli kolonları madde madde yaz.
- Kolon listesi için `- **KOLON_ADI** — ne işe yarar` formatını kullan.
- FCT_ fact tablo, DIM_ boyut tablo gibi isimlendirme kalıplarından anlam çıkar.
- "Açıklama:", "Özet:", "Öneri:" gibi bölüm başlıkları kullanma — doğrudan yanıtla."""

    response = _get_client().chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400,
    )

    return response.choices[0].message.content
