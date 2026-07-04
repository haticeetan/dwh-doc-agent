import os
import re
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
    """skills/ klasöründen .md dosyasını okur."""
    path = os.path.join(SKILLS_DIR, f"{skill_name}.md")
    if not os.path.exists(path):
        logger.warning(f"Skill bulunamadı: {path}")
        return ""
    return open(path, encoding="utf-8").read()


def build_prompt(
    table: str,
    schema: dict,
    deps: dict,
    skill: str,
    all_tables: list[str],
    sample_rows: list | None = None,
) -> str:
    """LLM'e gönderilecek prompt'u hazırlar."""

    # Kolon listesi
    col_lines = []
    for col in schema.get("columns", []):
        nullable = "NULL olabilir" if col.get("nullable") == "Y" else "NOT NULL"
        comment = f" — {col['comments']}" if col.get("comments") else ""
        col_lines.append(
            f"  - {col['column_name']} ({col['data_type']}) | {nullable}{comment}"
        )
    columns_text = "\n".join(col_lines) if col_lines else "  (bilgi yok)"

    # Constraint listesi
    constraint_lines = []
    for c in schema.get("constraints", []):
        ctype = {"P": "PRIMARY KEY", "U": "UNIQUE", "R": "FOREIGN KEY"}.get(
            c.get("constraint_type"), c.get("constraint_type")
        )
        ref = f" → {c['r_table_name']}" if c.get("r_table_name") else ""
        constraint_lines.append(f"  - {ctype}: {c['column_name']}{ref}")
    constraints_text = "\n".join(constraint_lines) if constraint_lines else "  (yok)"

    # Bu tabloyu kullanan DB nesneleri
    obj_lines = [
        f"  - {o['type']}: {o['name']}"
        for o in deps.get("used_by_objects", [])
    ]
    obj_text = "\n".join(obj_lines) if obj_lines else "  (yok)"

    # Örnek veri bölümü — yalnızca kullanıcı izin verdiyse ve veri geldiyse eklenir
    if sample_rows:
        sample_lines = []
        for i, row in enumerate(sample_rows, 1):
            sample_lines.append(f"  Satır {i}: {row}")
        sample_section = "### Örnek Veriler\n" + "\n".join(sample_lines)
    else:
        sample_section = ""

    # İlişkiler bölümü — YALNIZCA birden fazla tablo belgeleniyorsa ve
    # bu istekteki tablolar arasında bir bağlantı varsa eklenir
    relations_section = _build_relations_section(table, deps, schema, all_tables)

    return f"""Sen bir veri ambarı dokümantasyon uzmanısın.
Aşağıdaki Oracle tablosunu belgele.

{skill}

## Tablo Bilgisi

Tablo Adı: {table}

### Kolonlar
{columns_text}

### Constraint'ler
{constraints_text}

### Bu Tabloyu Kullanan DB Nesneleri
{obj_text}

{relations_section}{sample_section}
Yukarıdaki bilgilere dayanarak Türkçe, kapsamlı bir dokümantasyon yaz.
Sadece markdown formatında çıktı ver, başka hiçbir şey ekleme."""


_DWH_PREFIXES = {"DIM", "FACT", "FCT", "STAG", "STG", "REF", "LKP", "BRG", "AGG"}


def _strip_dwh_prefix(table_name: str) -> str:
    """DIM_CUSTOMER → CUSTOMER, FCT_SALES → SALES, ORDERS → ORDERS"""
    parts = table_name.split("_", 1)
    if len(parts) > 1 and parts[0] in _DWH_PREFIXES:
        return parts[1]
    return table_name


def _col_matches_table(col_base: str, table_name: str) -> bool:
    """
    CUSTOMER_ID'den türetilen 'CUSTOMER' → DIM_CUSTOMER eşleşir mi?
    Doğrudan eşleşme veya DWH prefiksi soyulunca eşleşme.
    """
    return col_base == table_name or col_base == _strip_dwh_prefix(table_name)


def _build_relations_section(table: str, deps: dict, schema: dict, all_tables: list[str]) -> str:
    """
    Yalnızca bu istekte belgelenen tablolar arasındaki ilişkileri döner.
    Tek tablo belgeleniyorsa boş string döner (İlişkiler bölümü oluşturulmaz).

    Tespit sırası:
      1. Onaylanmış FK constraint'leri
      2. dep_tracer'ın ürettiği örtük ilişkiler (tablo adı doğrudan eşleşiyorsa)
      3. Kolon adı → tablo adı eşleştirmesi (DWH DIM_/FACT_ prefiksleri soyularak)
         — DWH'larda FK constraint nadiren tanımlandığı için bu kat kritik
    """
    if len(all_tables) <= 1:
        return ""

    other_tables = set(all_tables) - {table}

    confirmed_lines = []
    for fk in deps.get("depends_on", []):
        if fk["table"] in other_tables:
            confirmed_lines.append(
                f"  - {fk['via_column']} → {fk['table']}.{fk['ref_column']} (onaylanmış FK)"
            )
    for ref in deps.get("referenced_by", []):
        if ref["table"] in other_tables:
            confirmed_lines.append(
                f"  - {ref['table']} bu tabloyu referans alıyor, "
                f"{ref['via_column']} kolonu üzerinden (onaylanmış FK)"
            )

    uncertain_lines = []
    already_linked = set()  # aynı tablo çiftini iki kez ekleme

    # dep_tracer'ın örtük ilişkileri — doğrudan isim eşleşmesi
    for rel in deps.get("implicit_relations", []):
        if rel["table"] in other_tables:
            uncertain_lines.append(
                f"  - {rel['via_column']} → {rel['table']} (FK tanımsız, isim benzerliği)"
            )
            already_linked.add(rel["table"])

    # Kolon adından tablo çıkarımı: CUSTOMER_ID → CUSTOMER → DIM_CUSTOMER
    for col in schema.get("columns", []):
        col_name = col["column_name"]
        if not col_name.endswith("_ID"):
            continue
        col_base = col_name[:-3]  # _ID çıkar
        for other in other_tables:
            if other in already_linked:
                continue
            if _col_matches_table(col_base, other):
                uncertain_lines.append(
                    f"  - {col_name} → {other} (FK tanımsız, kolon adı benzerliğiyle tahmin)"
                )
                already_linked.add(other)

    if not confirmed_lines and not uncertain_lines:
        return ""

    lines = []
    if confirmed_lines:
        lines.append("Onaylanmış ilişkiler:")
        lines.extend(confirmed_lines)
    if uncertain_lines:
        lines.append("Olası ilişkiler (kesin değil, FK constraint tanımsız):")
        lines.extend(uncertain_lines)

    other_list = ", ".join(sorted(other_tables))
    return f"""### Bu İstekteki Tablolarla İlişkiler
Belgelenen diğer tablolar: {other_list}
{chr(10).join(lines)}

"""


_CODE_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*\n(.*)\n```\s*$", re.DOTALL)


def _strip_code_fence(text: str) -> str:
    """
    GPT-4o, "sadece markdown formatında çıktı ver" talimatına çoğu zaman tüm
    yanıtı ```markdown ... ``` bloğuna sararak uyuyor. Bu saran fence satırları
    docx/pdf builder'lar tarafından tanınmıyor ve belgenin en üstünde düz metin
    olarak ("```markdown") görünüyor — bu yüzden burada temizleniyor.
    """
    text = text.strip()
    match = _CODE_FENCE_RE.match(text)
    return match.group(1).strip() if match else text


@openai_retry
def _generate_doc(prompt: str) -> str:
    """OpenAI'dan markdown döküman üretir. Geçici hatalarda retry decorator devreye girer."""
    response = _get_client().chat.completions.create(
        model="gpt-4o",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return _strip_code_fence(response.choices[0].message.content)


def doc_writer_node(state: DocAgentState) -> DocAgentState:
    """
    Her tablo için LLM'e prompt gönderip markdown döküman üretir.
    retry_count'u artırır.

    Girdi : state["schemas"], state["lineage"]
    Çıktı : state["draft_docs"], state["retry_count"]
    """
    tables = state.get("tables", [])
    schemas = state.get("schemas", {})
    lineage = state.get("lineage", {})
    sample_data = state.get("sample_data", {})
    draft_docs = state.get("draft_docs", {})
    retry_count = state.get("retry_count", 0)

    skill = load_skill("doc_template")

    for table in tables:
        schema = schemas.get(table, {})
        deps = lineage.get(table, {})
        sample_rows = sample_data.get(table)

        if not schema.get("columns"):
            logger.warning(f"{table} için schema yok, atlanıyor")
            continue

        logger.info(f"{table} için döküman üretiliyor (deneme {retry_count + 1})")

        prompt = build_prompt(table, schema, deps, skill, tables, sample_rows)

        draft_docs[table] = _generate_doc(prompt)
        logger.info(f"{table} dökümanı üretildi ({len(draft_docs[table])} karakter)")

    return {
        **state,
        "draft_docs": draft_docs,
        "retry_count": retry_count + 1,
    }