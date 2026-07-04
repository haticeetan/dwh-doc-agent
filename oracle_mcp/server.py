import logging
import re

from mcp.server.fastmcp import FastMCP

from oracle_mcp.oracle_client import execute_query

logger = logging.getLogger(__name__)

mcp = FastMCP("dw-docagent")


# ─────────────────────────────────────────────
# TOOL 1: schema_reader
# Tablo yapısını okur — kolonlar, tipler, constraint'ler, mevcut comment'ler
# ─────────────────────────────────────────────
@mcp.tool()
def schema_reader(table_name: str) -> dict:
    """
    Verilen tablonun yapısal bilgisini döner.
    Kolonlar, veri tipleri, nullable durumu ve mevcut Oracle comment'leri içerir.

    Args:
        table_name: Büyük harfle tablo adı — örnek: "ORDERS"

    Returns:
        {
          "table_name": str,
          "columns": [
            {
              "column_name": str,
              "data_type": str,
              "data_length": int,
              "nullable": "Y" | "N",
              "column_id": int,
              "comments": str | None
            }
          ],
          "constraints": [
            {
              "constraint_name": str,
              "constraint_type": "P" | "U" | "R" | "C",
              "column_name": str,
              "r_table_name": str | None   # FK ise referans aldığı tablo
            }
          ]
        }
    """
    table_name = table_name.upper()

    # Kolon bilgileri
    columns = execute_query(
        """
        SELECT
            col.column_id,
            col.column_name,
            col.data_type,
            col.data_length,
            col.data_precision,
            col.data_scale,
            col.nullable,
            com.comments
        FROM all_tab_columns col
        LEFT JOIN all_col_comments com
            ON  com.owner       = col.owner
            AND com.table_name  = col.table_name
            AND com.column_name = col.column_name
        WHERE col.table_name = :tname
        ORDER BY col.column_id
        """,
        {"tname": table_name}
    )

    if not columns:
        logger.warning(f"Tablo bulunamadı veya erişim yok: {table_name}")
        return {"table_name": table_name, "columns": [], "constraints": []}

    # Constraint bilgileri (PK, UK, FK)
    constraints = execute_query(
        """
        SELECT
            cc.constraint_name,
            c.constraint_type,
            cc.column_name,
            c.r_constraint_name,
            r_c.table_name AS r_table_name
        FROM all_cons_columns cc
        JOIN all_constraints c
            ON  c.constraint_name = cc.constraint_name
            AND c.owner           = cc.owner
        LEFT JOIN all_constraints r_c
            ON r_c.constraint_name = c.r_constraint_name
        WHERE cc.table_name      = :tname
          AND c.constraint_type IN ('P', 'U', 'R')
        ORDER BY c.constraint_type, cc.position
        """,
        {"tname": table_name}
    )

    return {
        "table_name": table_name,
        "columns": columns,
        "constraints": constraints
    }


# ─────────────────────────────────────────────
# TOOL 2: dep_tracer
# FK ve view/prosedür bağımlılıklarını izler
# ─────────────────────────────────────────────
@mcp.tool()
def dep_tracer(table_name: str) -> dict:
    """
    Tablonun upstream (bağımlı olduğu) ve downstream (kendisine bağımlı)
    ilişkilerini döner. FK constraint'leri ve view/prosedür bağımlılıklarını içerir.

    Args:
        table_name: Büyük harfle tablo adı — örnek: "ORDERS"

    Returns:
        {
          "table_name": str,
          "foreign_keys": [...],
          "referenced_by": [...],
          "used_by_objects": [...],
          "implicit_relations": [...]
        }
    """
    table_name = table_name.upper()

    # Bu tablonun FK'leri — referans aldığı tablolar
    foreign_keys = execute_query(
        """
        SELECT
            cc.column_name,
            r_c.table_name  AS r_table_name,
            r_cc.column_name AS r_column_name,
            c.constraint_name
        FROM all_cons_columns cc
        JOIN all_constraints c
            ON  c.constraint_name = cc.constraint_name
            AND c.constraint_type = 'R'
        JOIN all_constraints r_c
            ON r_c.constraint_name = c.r_constraint_name
        JOIN all_cons_columns r_cc
            ON  r_cc.constraint_name = r_c.constraint_name
            AND r_cc.position        = cc.position
        WHERE cc.table_name = :tname
        """,
        {"tname": table_name}
    )

    # Bu tabloyu referans alan diğer tablolar
    referenced_by = execute_query(
        """
        SELECT
            cc.table_name,
            cc.column_name,
            c.constraint_name
        FROM all_constraints c
        JOIN all_constraints r_c
            ON r_c.constraint_name = c.r_constraint_name
        JOIN all_cons_columns cc
            ON  cc.constraint_name = c.constraint_name
        WHERE r_c.table_name    = :tname
          AND c.constraint_type = 'R'
        """,
        {"tname": table_name}
    )

    # View, prosedür, trigger gibi nesnelerin bağımlılıkları
    used_by_objects = execute_query(
        """
        SELECT DISTINCT name, type
        FROM all_dependencies
        WHERE referenced_name = :tname
          AND referenced_type = 'TABLE'
          AND type NOT IN ('NON-EXISTENT')
        ORDER BY type, name
        """,
        {"tname": table_name}
    )

    # _ID ile biten kolonlar → FK tanımlanmamış olabilecek örtük ilişkiler
    implicit_relations = execute_query(
        """
        SELECT
            col.column_name,
            REPLACE(col.column_name, '_ID', '') AS possible_ref_table
        FROM all_tab_columns col
        WHERE col.table_name = :tname
          AND col.column_name LIKE :id_pattern
          AND col.column_name != :pk_col
          AND NOT EXISTS (
              SELECT 1
              FROM all_cons_columns cc
              JOIN all_constraints c
                  ON c.constraint_name = cc.constraint_name
                 AND c.constraint_type = 'R'
              WHERE cc.table_name  = col.table_name
                AND cc.column_name = col.column_name
          )
        """,
        {"tname": table_name, "id_pattern": "%_ID", "pk_col": table_name.rstrip("S") + "_ID"}
    )

    # Güven seviyesi: tahmin edilen tablo gerçekten var mı?
    enriched_implicit = []
    for rel in implicit_relations:
        possible_table = rel["possible_ref_table"]
        exists = execute_query(
            "SELECT COUNT(*) AS cnt FROM all_tables WHERE table_name = :tname",
            {"tname": possible_table}
        )
        confidence = "high" if exists[0]["cnt"] > 0 else "medium"
        enriched_implicit.append({
            "column_name": rel["column_name"],
            "possible_ref_table": possible_table,
            "confidence": confidence
        })

    return {
        "table_name": table_name,
        "foreign_keys": foreign_keys,
        "referenced_by": referenced_by,
        "used_by_objects": used_by_objects,
        "implicit_relations": enriched_implicit
    }


# ─────────────────────────────────────────────
# TOOL 3: ddl_audit
# Son DDL değişikliklerini okur
# ─────────────────────────────────────────────
@mcp.tool()
def ddl_audit(since_hours: int = 24) -> list[dict]:
    """
    Son N saatte yapılan DDL değişikliklerini listeler.
    CREATE TABLE, ALTER TABLE, DROP TABLE gibi değişiklikleri yakalar.

    Args:
        since_hours: Kaç saat geriye bakılacak — default 24

    Returns:
        [{"obj_name": str, "obj_type": str, "action": str, "timestamp": str, "db_user": str}]
    """
    changes = execute_query(
        """
        SELECT
            obj_name,
            obj_type,
            action,
            TO_CHAR(timestamp, 'YYYY-MM-DD HH24:MI:SS') AS timestamp,
            db_user
        FROM dba_audit_trail
        WHERE action_name IN ('CREATE TABLE', 'ALTER TABLE', 'DROP TABLE',
                              'CREATE INDEX', 'DROP INDEX')
          AND timestamp >= SYSDATE - (:hours / 24)
        ORDER BY timestamp DESC
        """,
        {"hours": since_hours}
    )

    if not changes:
        logger.info(f"Son {since_hours} saatte DDL değişikliği bulunamadı.")

    return changes


# ─────────────────────────────────────────────
# TOOL 4: sample_fetcher
# Kolon semantiğini anlamak için örnek veri çeker
# ─────────────────────────────────────────────
@mcp.tool()
def sample_fetcher(table_name: str, limit: int = 5) -> dict:
    """
    Tablodan örnek satırlar çeker. LLM'in kolon içeriğini anlamasına yardımcı olur.
    Örnek: bir kolon 0/1 değer alıyorsa boolean flag olduğu anlaşılır.

    Args:
        table_name: Büyük harfle tablo adı — örnek: "ORDERS"
        limit:      Kaç satır çekileceği — default 5, max 20

    Returns:
        {"table_name": str, "row_count": int, "sample_rows": list}
    """
    table_name = table_name.upper()
    limit = min(limit, 20)  # maksimum 20 satır

    # Toplam satır sayısı (istatistikten, hızlı)
    count_result = execute_query(
        "SELECT num_rows FROM all_tables WHERE table_name = :tname",
        {"tname": table_name}
    )
    row_count = count_result[0]["num_rows"] if count_result else None

    # all_tables sorgusuyla tablo varlığını doğrula; tablo adı bind variable
    # desteklemediğinden tırnak içine alınarak interpolasyon güvenli hale getirilir.
    if not count_result:
        return {"table_name": table_name, "row_count": None, "sample_rows": []}

    sample_rows = execute_query(
        f'SELECT * FROM "{table_name}" FETCH FIRST :lmt ROWS ONLY',
        {"lmt": limit}
    )

    return {
        "table_name": table_name,
        "row_count": row_count,
        "sample_rows": sample_rows,
    }


# ─────────────────────────────────────────────
# TOOL 5: table_search
# Tablo adı veya comment içinde anahtar kelime araması
# ─────────────────────────────────────────────
@mcp.tool()
def table_search(keywords: list[str]) -> list[dict]:
    """
    Tablo adı veya tablo comment'i içinde anahtar kelime araması yapar.
    Veritabanı keşfi senaryolarında kullanılır.

    Args:
        keywords: Arama anahtar kelimeleri — örnek: ["satış", "sipariş", "SALES"]

    Returns:
        [{"table_name": str, "comments": str | None}]
    """
    if not keywords:
        return []

    # Tehlikeli karakterleri temizle (tırnak, noktalı virgül, ters eğik çizgi)
    clean = [re.sub(r"['\";\\]", "", kw).upper().strip() for kw in keywords]
    clean = [kw for kw in clean if kw]
    if not clean:
        return []

    name_clauses, comment_clauses, params = [], [], {}
    for i, kw in enumerate(clean):
        name_clauses.append(f"UPPER(t.table_name) LIKE :kw{i}")
        comment_clauses.append(f"UPPER(tc.comments) LIKE :ckw{i}")
        params[f"kw{i}"] = f"%{kw}%"
        params[f"ckw{i}"] = f"%{kw}%"

    name_clause = " OR ".join(name_clauses)
    comment_clause = " OR ".join(comment_clauses)

    results = execute_query(
        f"""
        SELECT DISTINCT
            t.table_name,
            tc.comments
        FROM all_tables t
        LEFT JOIN all_tab_comments tc
            ON  tc.table_name = t.table_name
            AND tc.owner      = t.owner
        WHERE ({name_clause})
           OR ({comment_clause})
        ORDER BY t.table_name
        """,
        params
    )

    return results


# ─────────────────────────────────────────────
# TOOL 6: table_lister
# Veritabanındaki erişilebilir tüm tabloları listeler
# ─────────────────────────────────────────────
@mcp.tool()
def table_lister() -> list[dict]:
    """
    Veritabanında erişim yetkisi olan tüm tabloları listeler.
    Anahtar kelime filtresi olmadan table_search'ün filtresiz hali.

    Returns:
        [{"table_name": str, "comments": str | None}]
    """
    results = execute_query(
        """
        SELECT
            t.table_name,
            tc.comments
        FROM all_tables t
        LEFT JOIN all_tab_comments tc
            ON  tc.table_name = t.table_name
            AND tc.owner      = t.owner
        ORDER BY t.table_name
        """,
        {}
    )

    logger.info(f"{len(results)} tablo listelendi")
    return results


if __name__ == "__main__":
    mcp.run()
