import os
from openai import OpenAI
from agent.state import DocAgentState
from logger import get_logger
from resilience import openai_retry

logger = get_logger(__name__)
SKILLS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "skills")
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def load_skill(skill_name: str) -> str:
    path = os.path.join(SKILLS_DIR, f"{skill_name}.md")
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()


@openai_retry
def _score_with_llm(prompt: str) -> str:
    """Kalite puanı için OpenAI'ı çağırır. Geçici hatalarda retry decorator devreye girer."""
    response = _get_client().chat.completions.create(
        model="gpt-4o",
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


def score_document(doc_text: str, schema: dict, skill: str) -> float:
    """LLM-as-judge pattern ile dökümanı 0.0 - 1.0 arası puanlar."""
    col_names = [c["column_name"] for c in schema.get("columns", [])]

    prompt = f"""{skill}

Aşağıdaki tablo dokümantasyonunu değerlendir ve SADECE 0.00 ile 1.00 arasında
bir sayı yaz. Başka hiçbir şey yazma.

Değerlendirme kriterleri:
- Tüm kolonlar belgelenmiş mi? (0.4 ağırlık)
  Beklenen kolonlar: {', '.join(col_names)}
- İlişkiler açıklanmış mı? (0.3 ağırlık)
- Genel tablo amacı anlatılmış mı? (0.3 ağırlık)

Döküman:
{doc_text}

Puan (sadece sayı, örnek: 0.85):"""

    raw = _score_with_llm(prompt)
    try:
        score = float(raw)
        return max(0.0, min(1.0, score))
    except ValueError:
        logger.warning(f"Skor parse edilemedi: '{raw}', 0.5 varsayıldı")
        return 0.5


def quality_checker_node(state: DocAgentState) -> DocAgentState:
    """
    Her draft_doc için kalite puanı hesaplar.
    Tüm tablolar 0.7 üstü puan alırsa approved=True.
    """
    draft_docs = state.get("draft_docs", {})
    schemas = state.get("schemas", {})
    quality_scores = {}

    skill = load_skill("quality_scorer")

    for table, doc in draft_docs.items():
        schema = schemas.get(table, {})
        score = score_document(doc, schema, skill)
        quality_scores[table] = score
        if score >= 0.7:
            logger.info(f"{table} kalite skoru: {score:.2f} — onaylandı")
        else:
            logger.warning(f"{table} kalite skoru: {score:.2f} — eşiğin altında (0.7)")

    approved = all(s >= 0.7 for s in quality_scores.values())

    final_markdown = ""
    if approved or state.get("retry_count", 0) >= 1:
        parts = list(draft_docs.values())

        # Kısmi eksiklik: istenen tablolardan bazıları bulunamadıysa uyarı ekle
        requested = state.get("tables", [])
        missing = [t for t in requested if t not in draft_docs]
        if missing:
            missing_note = (
                "> **Uyarı:** "
                + ", ".join(f"`{t}`" for t in missing)
                + " tablosu veritabanında bulunamadı veya erişim izni yok — belgelenemedi."
            )
            parts.insert(0, missing_note)

        final_markdown = "\n\n---\n\n".join(parts)

    return {
        **state,
        "quality_scores": quality_scores,
        "approved": approved,
        "final_markdown": final_markdown,
    }