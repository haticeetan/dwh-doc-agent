import io
import os
import re
import warnings
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

# ── Unicode font kaydı ──────────────────────────────────────────────────────────
# ReportLab'in yerleşik Helvetica fontu Türkçe'ye özgü ğ/ş/ı/İ karakterlerini
# içermiyor (WinAnsi kodlaması). Sistemde Arial varsa onu kaydedip kullanıyoruz;
# yoksa (örn. Linux/CI) sessizce Helvetica'ya düşüyoruz — Türkçe karakterler o
# durumda yine render edilemez, bu durum bilinen bir kısıtlama olarak kalır.
_FONT_REGULAR = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"

_ARIAL_REGULAR = r"C:\Windows\Fonts\arial.ttf"
_ARIAL_BOLD = r"C:\Windows\Fonts\arialbd.ttf"

if os.path.exists(_ARIAL_REGULAR) and os.path.exists(_ARIAL_BOLD):
    pdfmetrics.registerFont(TTFont("Arial", _ARIAL_REGULAR))
    pdfmetrics.registerFont(TTFont("Arial-Bold", _ARIAL_BOLD))
    _FONT_REGULAR = "Arial"
    _FONT_BOLD = "Arial-Bold"
else:
    warnings.warn(
        "Arial fontu bulunamadı — PDF'lerde Türkçe karakterler (ğ, ş, ı, İ) "
        "düzgün görüntülenmeyecek. Kalıcı çözüm için Unicode destekli bir "
        "TTF font projeye gömülüp burada kaydedilmeli."
    )


# ── Stil tanımları ─────────────────────────────────────────────────────────────
def _get_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="DWDocTitle",
        fontSize=20, leading=24, spaceAfter=12,
        textColor=colors.HexColor("#2E74B5"), fontName=_FONT_BOLD
    ))
    styles.add(ParagraphStyle(
        name="DWHeading2",
        fontSize=14, leading=18, spaceAfter=6, spaceBefore=12,
        textColor=colors.HexColor("#2E74B5"), fontName=_FONT_BOLD
    ))
    styles.add(ParagraphStyle(
        name="DWHeading3",
        fontSize=12, leading=16, spaceAfter=4, spaceBefore=8,
        textColor=colors.HexColor("#404040"), fontName=_FONT_BOLD
    ))
    styles.add(ParagraphStyle(
        name="DWBody",
        fontSize=10, leading=14, spaceAfter=4,
        textColor=colors.HexColor("#1A1A1A"), fontName=_FONT_REGULAR
    ))
    return styles


def _parse_markdown_table(lines: list[str]) -> list[list[str]]:
    """Markdown tablo satırlarını 2D liste'ye çevirir."""
    rows = [l for l in lines if l.strip().startswith("|") and "---" not in l]
    return [
        [c.strip() for c in row.strip().strip("|").split("|")]
        for row in rows
    ]


def _build_pdf_table(data: list[list[str]], styles) -> Table:
    """
    ReportLab Table objesi üretir.

    Hücreler düz string yerine Paragraph'a sarılır — Table, düz string hücrelerde
    satır kaydırma yapmaz ve uzun açıklamalar kolon sınırının dışına taşar.
    Son kolon (genelde "Açıklama") diğerlerine göre iki kat geniş tutulur çünkü
    doc_template.md'deki tablo formatında en uzun metni her zaman o taşır.
    """
    if not data:
        return None

    col_count = len(data[0])
    available_width = A4[0] - 4 * cm

    weights = [1] * (col_count - 1) + [2] if col_count > 1 else [1]
    total_weight = sum(weights)
    col_widths = [available_width * w / total_weight for w in weights]

    header_style = ParagraphStyle(
        "DWTableHeader", parent=styles["DWBody"],
        textColor=colors.white, fontName=_FONT_BOLD, fontSize=9, leading=11,
    )
    cell_style = ParagraphStyle(
        "DWTableCell", parent=styles["DWBody"],
        fontName=_FONT_REGULAR, fontSize=9, leading=11,
    )

    wrapped_data = [
        [
            Paragraph(_xml_escape(cell), header_style if row_idx == 0 else cell_style)
            for cell in row
        ]
        for row_idx, row in enumerate(data)
    ]

    table = Table(wrapped_data, colWidths=col_widths)
    table.setStyle(TableStyle([
        # Başlık satırı
        ("BACKGROUND",   (0, 0), (-1, 0),  colors.HexColor("#2E74B5")),
        # Veri satırları
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F7FC")]),
        # Genel
        ("GRID",         (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    return table


def _parse_and_render(markdown: str, styles) -> list:
    """Markdown satırlarını ReportLab Flowable listesine dönüştürür."""
    elements = []
    lines = markdown.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]

        # Başlıklar
        if line.startswith("# "):
            elements.append(Paragraph(_xml_escape(line[2:].strip()), styles["DWDocTitle"]))
        elif line.startswith("## "):
            elements.append(Paragraph(_xml_escape(line[3:].strip()), styles["DWHeading2"]))
        elif line.startswith("### "):
            elements.append(Paragraph(_xml_escape(line[4:].strip()), styles["DWHeading3"]))
        elif line.startswith("#### "):
            elements.append(Paragraph(_xml_escape(line[5:].strip()), styles["DWHeading3"]))

        # Markdown tablo
        elif line.strip().startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            data = _parse_markdown_table(table_lines)
            if data:
                pdf_table = _build_pdf_table(data, styles)
                if pdf_table:
                    elements.append(pdf_table)
                    elements.append(Spacer(1, 0.3 * cm))
            continue

        # Yatay çizgi
        elif line.strip() in ("---", "***", "___"):
            elements.append(HRFlowable(width="100%", thickness=0.5,
                                       color=colors.HexColor("#CCCCCC")))

        # Boş satır
        elif line.strip() == "":
            elements.append(Spacer(1, 0.2 * cm))

        # Normal paragraf — önce XML özel karakterlerini kaçır (&, <, > ReportLab'in
        # mini XML ayrıştırıcısı tarafından etiket sanılıp sessizce yutulabiliyor),
        # sonra **kalın** işaretini gerçek <b> etiketine dönüştür
        else:
            escaped = _xml_escape(line)
            text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)
            elements.append(Paragraph(text, styles["DWBody"]))

        i += 1

    return elements


def build_pdf(markdown_text: str, title: str = "Tablo Dokümantasyonu") -> bytes:
    """
    Markdown metni alır, PDF belgesi üretir, bytes olarak döner.

    Args:
        markdown_text: doc_writer'ın ürettiği markdown içerik
        title:         Belge başlığı (tablo adı)

    Returns:
        .pdf dosyasının byte içeriği
    """
    buffer = io.BytesIO()
    styles = _get_styles()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2 * cm,
        title=title,
        author="DW-DocAgent",
    )

    elements = _parse_and_render(markdown_text, styles)
    doc.build(elements)

    buffer.seek(0)
    return buffer.read()