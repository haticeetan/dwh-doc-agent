import os
import re
import time
import uuid
from datetime import datetime

from output.docx_builder import build_docx
from output.pdf_builder import build_pdf
from logger import get_logger

logger = get_logger(__name__)

TEMP_DIR = os.path.join(os.path.dirname(__file__), "..", "tmp", "docagent")
FILE_TTL_SECONDS = 3600  # 1 saat


def _ensure_temp_dir():
    os.makedirs(TEMP_DIR, exist_ok=True)


def _sanitize_filename(text: str) -> str:
    """Tablo adını dosya adı için güvenli hale getirir (örn. 'FACT_SALES, FACT_RETURNS' → 'FACT_SALES_FACT_RETURNS')."""
    text = re.sub(r"[,\s]+", "_", text.strip())
    text = re.sub(r"[^\w\-]", "", text, flags=re.UNICODE)
    text = text.strip("_") or "dokumantasyon"
    return text[:60]


def generate_document(final_markdown: str, output_format: str, title: str) -> str:
    """
    Graph'ın ürettiği markdown'ı docx veya pdf'e dönüştürür,
    geçici dizine kaydeder ve job_id döner.

    Args:
        final_markdown: quality_checker'ın onayladığı birleşik markdown
        output_format:  "docx" veya "pdf"
        title:          Dosya adı için kullanılacak tablo adı

    Returns:
        job_id — dosya adının uzantısız hali (tablo_adı_tarih_saat_kısa-kod),
        /download/{job_id} endpoint'inde kullanılır
    """
    _ensure_temp_dir()
    cleanup_old_files()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = _sanitize_filename(title)
    # Aynı saniyede aynı tablo tekrar belgelenirse çakışmayı önlemek için kısa bir kod eklenir
    job_id = f"{safe_title}_{timestamp}_{uuid.uuid4().hex[:6]}"

    if output_format == "pdf":
        file_bytes = build_pdf(final_markdown, title)
        ext = "pdf"
    else:
        file_bytes = build_docx(final_markdown, title)
        ext = "docx"

    filename = f"{job_id}.{ext}"
    filepath = os.path.join(TEMP_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(file_bytes)

    logger.info(f"Dosya oluşturuldu: {filename} ({len(file_bytes)} byte)")
    return job_id


def get_file_path(job_id: str) -> str | None:
    """
    job_id'ye karşılık gelen dosya yolunu döner.
    Dosya yoksa None döner.
    """
    _ensure_temp_dir()
    for fname in os.listdir(TEMP_DIR):
        if fname.startswith(job_id):
            return os.path.join(TEMP_DIR, fname)
    return None


def get_file_extension(job_id: str) -> str | None:
    """job_id'ye ait dosyanın uzantısını döner."""
    path = get_file_path(job_id)
    if path:
        return os.path.splitext(path)[1].lstrip(".")
    return None


def cleanup_old_files():
    """TTL süresi dolan geçici dosyaları siler."""
    _ensure_temp_dir()
    now = time.time()
    count = 0
    for fname in os.listdir(TEMP_DIR):
        fpath = os.path.join(TEMP_DIR, fname)
        if os.path.isfile(fpath):
            age = now - os.path.getmtime(fpath)
            if age > FILE_TTL_SECONDS:
                os.remove(fpath)
                count += 1
    if count:
        logger.info(f"{count} eski dosya silindi (TTL: {FILE_TTL_SECONDS}s)")