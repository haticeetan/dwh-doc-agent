import re
from enum import Enum
from pydantic import BaseModel
from openai import OpenAI

from agent.state import DocAgentState
from agent.conversation_store import get_history
from logger import get_logger
from resilience import openai_retry

logger = get_logger(__name__)
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


class IntentType(str, Enum):
    CHITCHAT = "chitchat"
    DISCOVERY = "discovery"
    TABLE_INFO = "table_info"
    DOCUMENT = "document"
    CONSENT_YES = "consent_yes"
    CONSENT_NO = "consent_no"


class ParsedIntent(BaseModel):
    intent_type: IntentType
    tables: list[str]
    topic_keywords: list[str]
    output_format: str
    chitchat_response: str
    confidence: float


_SYSTEM_PROMPT = """Sen bir veri ambarı (DWH) dokümantasyon asistanısın. Oracle tabanlı kurumsal bir veri ambarı için çalışıyorsun.

Kullanıcının mesajını analiz et ve niyetini tam olarak belirle. Altı seçenekten biri olabilir:

1. **chitchat** — İki alt grup vardır, her ikisi de chitchat döner:
   a) Görevle ilgili küçük konuşma: selamlama, teşekkür, yetenek sorusu, onay.
      Örnekler: "Merhaba", "Nasılsın?", "Sen ne yaparsın?", "Teşekkürler", "Tamam", "Anladım"
      → chitchat_response: kısa ve samimi yanıt.
   b) Tamamen konu dışı soru: veri ambarı ile hiç ilgisi olmayan her konu (hava durumu, moda, yemek, sağlık vb.).
      Örnekler: "Yarın ne giysem?", "Bugün hava nasıl?", "Bana şiir yaz"
      → chitchat_response: "Ben bir veri ambarı dokümantasyon asistanıyım, bu konu görev alanımın dışında. Oracle tablolarını belgelemek, keşfetmek veya sorgulamak için buradayım."

2. **discovery** — Belirli bir tablo adı belirtmeden genel keşif: kaç tablo var, hangi tablolar belirli bir konuyla ilgili.
   Örnekler: "Satış ile ilgili tablolar hangileri?", "Reklam gelirimizi hangi tablolardan hesaplarız?", "Veritabanında kaç tablo var?"

3. **table_info** — Belirli, ismi bilinen bir tablonun içeriğini, yapısını veya amacını soran bilgi sorusu.
   Belgeleme talebi değil; "ne içeriyor", "ne işe yarıyor", "nasıl bir tablo", "hangi kolonlar var" gibi ifadeler.
   Örnekler: "DIM_PRODUCT tablosu ne tür veriler içeriyor?", "ORDERS tablosu ne işe yarıyor?", "FACT_SALES'in kolonları neler?"

4. **document** — Belirli tabloların tam belgelenmesi talebi. "Belgele", "doküman oluştur", "dökümante et", "PDF/DOCX hazırla" gibi açık eylemler içerir.
   Örnekler: "FACT_SALES tablosunu belgele", "DIM_CUSTOMER için PDF hazırla", "orders tablosunu dökümante et"

5. **consent_yes** — Kullanıcı örnek veri kullanımına onay verdi.
   Örnekler: "Evet", "Evet kullan", "Kullanabilirsin", "Tabii ki", "Olur"

6. **consent_no** — Kullanıcı örnek veri kullanımını reddetti.
   Örnekler: "Hayır", "Hayır kullanma", "Gerek yok", "İstemiyorum"

Doldurma kuralları:
- **chitchat** için: Görevle ilgili küçük konuşmada kısa ve samimi yanıt; konu dışı sorularda "Ben bir veri ambarı dokümantasyon asistanıyım, bu konu görev alanımın dışında..." formatında yanıt → chitchat_response. tables=[], topic_keywords=[].
- **discovery** için: Konuyla ilgili anahtar kelimeleri çıkar → topic_keywords. tables=[]. chitchat_response="".
- **table_info** için: Tablo adını BÜYÜK HARFLE çıkar → tables. topic_keywords=[]. chitchat_response="".
- **document** için: Tablo adlarını BÜYÜK HARFLE çıkar → tables. topic_keywords=[]. chitchat_response="".
- **consent_yes** / **consent_no** için: tables=[], topic_keywords=[], chitchat_response="".
- output_format: Mesajda "pdf" geçiyorsa "pdf", aksi halde "docx".
- confidence: Mesajın niyetinin ne kadar net olduğu (0.0–1.0)."""


def intent_parser_node(state: DocAgentState) -> DocAgentState:
    """
    Graph'ın ilk node'u.
    Kullanıcı mesajını LLM ile analiz eder; chitchat / discovery / document olarak sınıflandırır.

    Girdi : state["message"]
    Çıktı : state["intent_type"], state["tables"], state["output_format"],
            state["chitchat_response"]
    """
    # Consent hızlı yolu — frontend'deki Evet/Hayır butonu tıklandığında
    # LLM çağrısına hiç gitmeden direkt sınıflandırma yapılır (2-3 sn tasarruf).
    consent = state.get("consent", "")
    if consent in ("yes", "no"):
        intent_type = IntentType.CONSENT_YES if consent == "yes" else IntentType.CONSENT_NO
        logger.info(f"Consent hızlı yolu: {intent_type} (LLM atlandı)")
        return {
            **state,
            "intent_type": intent_type,
            "tables": [],
            "chitchat_response": "",
            "discovery_result": "",
            "retry_count": 0,
            "schemas": {},
            "lineage": {},
            "sample_data": {},
            "draft_docs": {},
            "quality_scores": {},
            "final_markdown": "",
            "approved": False,
        }

    message = state.get("message", "")
    session_id = state.get("session_id", "")
    history = get_history(session_id)

    parsed = _classify_with_llm(message, history)
    if parsed is None:
        parsed = _regex_fallback(message)

    logger.info(
        f"Intent: {parsed.intent_type} | "
        f"Tablolar: {parsed.tables} | "
        f"Keywords: {parsed.topic_keywords} | "
        f"Güven: {parsed.confidence:.2f}"
    )

    return {
        **state,
        "intent_type": parsed.intent_type,
        "tables": parsed.tables,
        "output_format": parsed.output_format,
        "chitchat_response": parsed.chitchat_response,
        "discovery_result": "",
        "retry_count": 0,
        "schemas": {},
        "lineage": {},
        "draft_docs": {},
        "quality_scores": {},
        "final_markdown": "",
        "approved": False,
    }


@openai_retry
def _call_openai_parse(message: str, history: list[dict]) -> ParsedIntent:
    """Yapılandırılmış çıktı için OpenAI API'sini çağırır. Retry decorator tarafından korunur."""
    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    response = _get_client().beta.chat.completions.parse(
        model="gpt-4o",
        messages=messages,
        response_format=ParsedIntent,
        max_tokens=500,
    )
    return response.choices[0].message.parsed


def _classify_with_llm(message: str, history: list[dict]) -> ParsedIntent | None:
    """
    Retry'lar dahil tüm denemeler tükendikten sonra hata oluşursa
    None döner; çağıran regex fallback'e yönlenir.
    """
    try:
        return _call_openai_parse(message, history)
    except Exception as e:
        logger.warning(f"LLM sınıflandırması başarısız, fallback'e geçiliyor: {e}")
        return None


def _regex_fallback(message: str) -> ParsedIntent:
    """
    LLM çağrısı başarısız olursa devreye girer.
    Varsayım: tablo adı bulunabiliyorsa DOCUMENT, aksi halde CHITCHAT.
    """
    tables = _extract_tables(message)
    output_format = "pdf" if "pdf" in message.lower() else "docx"

    if tables:
        return ParsedIntent(
            intent_type=IntentType.DOCUMENT,
            tables=tables,
            topic_keywords=[],
            output_format=output_format,
            chitchat_response="",
            confidence=0.5,
        )

    return ParsedIntent(
        intent_type=IntentType.CHITCHAT,
        tables=[],
        topic_keywords=[],
        output_format=output_format,
        chitchat_response="Merhaba! DWH tablolarını belgelemene veya veritabanını keşfetmene yardımcı olabilirim.",
        confidence=0.3,
    )


def _extract_tables(message: str) -> list[str]:
    stopwords = {"PDF", "DOCX", "SQL", "VE", "ILE", "THE", "AND", "FOR",
                 "VEYA", "OR", "TABLE", "TABLO", "BELGELE", "YAZAR"}

    tables = [w for w in re.findall(r'\b[A-Z][A-Z0-9_]{2,}\b', message)
              if w not in stopwords]

    if not tables:
        tables = [t.upper() for t in re.findall(r'["\']([a-zA-Z][a-zA-Z0-9_]+)["\']', message)]

    if not tables:
        tables = [t.upper() for t in re.findall(
            r'(\w+)\s+tablo(?:su|yu|ları|larını)?', message, re.IGNORECASE
        )]

    return list(dict.fromkeys(tables))
