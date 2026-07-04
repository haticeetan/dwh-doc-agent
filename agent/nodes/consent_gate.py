from agent.state import DocAgentState
from agent.consent_store import store_pending, get_pending, clear_pending
from logger import get_logger
from oracle_mcp.oracle_client import execute_query

logger = get_logger(__name__)


def _missing_tables(tables: list[str]) -> list[str]:
    """Oracle'da var olmayan veya erişilemeyen tabloları döner."""
    missing = []
    for table in tables:
        result = execute_query(
            "SELECT COUNT(*) AS cnt FROM all_tables WHERE table_name = :tname",
            {"tname": table},
        )
        if not result or result[0]["cnt"] == 0:
            missing.append(table)
    return missing

def _build_consent_question(tables: list[str]) -> str:
    table_list = ", ".join(f"**{t}**" for t in tables)
    if len(tables) > 1:
        return (
            f"{table_list} tabloları için dokümantasyon hazırlayacağım.\n\n"
            "Kolon açıklamalarını daha doğru üretmek için her tablodan **ilk 5 satırı** "
            "örnek veri olarak kullanabilir miyim? "
            "Veriler yalnızca bu belgeleme işlemi için LLM'e iletilecektir."
        )
    return (
        f"{table_list} tablosu için dokümantasyon hazırlayacağım.\n\n"
        "Kolon açıklamalarını daha doğru üretmek için tablodan **ilk 5 satırı** "
        "örnek veri olarak kullanabilir miyim? "
        "Veriler yalnızca bu belgeleme işlemi için LLM'e iletilecektir."
    )


def consent_gate_node(state: DocAgentState) -> DocAgentState:
    """
    İki aşamalı örnek veri onay akışını yönetir.

    Senaryo A — Kullanıcı tablo belgeleme isteği gönderdi (intent==document):
        Tablo ve format bilgisini consent_store'a kaydeder, kullanıcıya onay sorusu
        yazar, waiting_consent=True ile END'e gider.

    Senaryo B — Kullanıcı onay yanıtı gönderdi (intent==consent_yes/consent_no):
        Store'dan bekleyen tablo bilgisini alır, use_sample_data'yı ayarlar,
        intent_type'ı "document"a döndürür ve belgeleme akışına devam eder.

    Senaryo C — chitchat veya discovery:
        Değişiklik yapmadan geçirir.
    """
    intent_type = state.get("intent_type", "")
    session_id = state.get("session_id", "")

    # ── Senaryo A: tablo belgeleme isteği → önce tablo kontrolü, sonra izin sor ──
    if intent_type == "document":
        tables = state.get("tables", [])
        output_format = state.get("output_format", "docx")

        # İzin sormadan önce tabloların Oracle'da var olup olmadığını kontrol et
        missing = _missing_tables(tables)
        if missing:
            found = [t for t in tables if t not in missing]
            if not found:
                # Hiçbir tablo bulunamadı — izin sorma, hata mesajı dön
                missing_list = ", ".join(f"**{t}**" for t in missing)
                logger.warning(f"Hiçbir tablo bulunamadı | session={session_id} | tablolar={missing}")
                return {
                    **state,
                    "waiting_consent": False,
                    "intent_type": "chitchat",
                    "chitchat_response": (
                        f"{missing_list} tablosu veritabanında bulunamadı veya "
                        "bu kullanıcıyla erişim izni yok. Tablo adını kontrol edip tekrar deneyin."
                    ),
                }
            # Bazı tablolar bulunamadı — bulunanlarla devam et
            missing_list = ", ".join(f"**{t}**" for t in missing)
            logger.warning(f"Bazı tablolar bulunamadı | session={session_id} | eksik={missing} | devam={found}")
            tables = found

        store_pending(session_id, tables, output_format)
        question = _build_consent_question(tables)
        if missing:
            question += (
                f"\n\n⚠️ Not: {missing_list} tablosu veritabanında bulunamadı — "
                "yalnızca bulunan tablolar belgelenecek."
            )

        logger.info(f"Örnek veri izni soruluyor | session={session_id} | tablolar={tables}")
        return {
            **state,
            "tables": tables,
            "waiting_consent": True,
            "consent_question": question,
        }

    # ── Senaryo B: onay yanıtı → akışa devam et ──────────────────────────────
    if intent_type in ("consent_yes", "consent_no"):
        pending = get_pending(session_id)

        if pending is None:
            logger.warning(f"Bekleyen istek bulunamadı | session={session_id}")
            return {
                **state,
                "intent_type": "chitchat",
                "chitchat_response": (
                    "Onay isteğine ait belgeleme talebini bulamadım. "
                    "Bu durum genellikle sunucunun yeniden başlatılmasıyla oluşur — "
                    "bekleyen talepler bellekte tutulduğu için kaybolur.\n\n"
                    "Lütfen belgeleme talebini tekrar gönderin. "
                    "Örnek: **'FACT_RETURNS tablosunu belgele'**"
                ),
                "waiting_consent": False,
            }

        clear_pending(session_id)
        use_sample = intent_type == "consent_yes"
        logger.info(
            f"Onay alındı | session={session_id} | "
            f"örnek_veri={'evet' if use_sample else 'hayır'} | "
            f"tablolar={pending['tables']}"
        )

        return {
            **state,
            "intent_type": "document",
            "tables": pending["tables"],
            "output_format": pending["output_format"],
            "use_sample_data": use_sample,
            "waiting_consent": False,
            "schemas": {},
            "lineage": {},
            "sample_data": {},
            "draft_docs": {},
            "quality_scores": {},
            "final_markdown": "",
            "approved": False,
            "retry_count": 0,
        }

    # ── Senaryo C: chitchat / discovery → geç ────────────────────────────────
    return {**state, "waiting_consent": False}
