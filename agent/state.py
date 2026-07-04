from typing import TypedDict


class DocAgentState(TypedDict):
    # ── Oturum ───────────────────────────────────────────────────────────────
    session_id: str           # Frontend'in ürettiği UUID; oturumlar arası state eşleştirme
    consent: str              # "yes" | "no" | "" — buton tıklandığında LLM atlanır

    # ── Girdi ────────────────────────────────────────────────────────────────
    message: str              # Kullanıcının ham mesajı

    # ── Intent ───────────────────────────────────────────────────────────────
    intent_type: str          # "chitchat" | "discovery" | "table_info" | "document" | "consent_yes" | "consent_no"
    chitchat_response: str    # chitchat durumunda LLM'in ürettiği yanıt
    discovery_result: str     # discovery node'unun ürettiği açıklama

    # ── Belgeleme girdileri ───────────────────────────────────────────────────
    tables: list[str]         # intent_parser'ın çıkardığı tablo adları
    output_format: str        # "docx" veya "pdf"

    # ── Örnek veri onayı ──────────────────────────────────────────────────────
    waiting_consent: bool     # True → kullanıcıdan onay bekleniyor, graph END'e gider
    use_sample_data: bool     # True → kullanıcı örnek veriye onay verdi
    consent_question: str     # waiting_consent=True olduğunda kullanıcıya gönderilecek mesaj

    # ── Oracle verisi ─────────────────────────────────────────────────────────
    schemas: dict             # {tablo_adı: schema_reader çıktısı}
    lineage: dict             # {tablo_adı: dep_tracer çıktısı}
    sample_data: dict         # {tablo_adı: örnek satır listesi} — use_sample_data=True ise dolu

    # ── Döküman üretimi ───────────────────────────────────────────────────────
    draft_docs: dict          # {tablo_adı: LLM'in ürettiği markdown}
    quality_scores: dict      # {tablo_adı: 0.0 - 1.0 arası puan}
    final_markdown: str       # Onaylanan ve birleştirilen son içerik
    approved: bool            # quality_checker onayladı mı

    # ── Döngü koruması ────────────────────────────────────────────────────────
    retry_count: int          # doc_writer kaç kez çalıştı