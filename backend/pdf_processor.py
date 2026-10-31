import hashlib
import re
from pathlib import Path
from typing import Optional

import pdfplumber
import pypdfium2 as pdfium
from PIL import Image, ImageDraw
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

from backend.config import PAGE_CACHE_DIR
from backend.verifier import normalize_with_index


def extract_pdf_pages(pdf_path: str | Path) -> list[str]:
    with pdfplumber.open(str(pdf_path)) as document:
        return [page.extract_text(layout=False) or "" for page in document.pages]


def sha256_file(pdf_path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(pdf_path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_demo_judgment_pdf(
    output_path: str | Path,
    court_name: str,
    case_title: str,
    paragraphs: list[str],
    decision_date: str,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="CourtHeader", parent=styles["Heading2"], alignment=TA_CENTER,
        fontName="Times-Bold", fontSize=13, leading=17, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="JudgmentBody", parent=styles["BodyText"], fontName="Times-Roman",
        fontSize=10.5, leading=16, alignment=4, spaceAfter=11,
    ))
    styles.add(ParagraphStyle(
        name="CaseTitle", parent=styles["Heading3"], alignment=TA_CENTER,
        fontName="Times-Bold", fontSize=11, leading=15,
    ))
    document = SimpleDocTemplate(
        str(path), pagesize=A4,
        rightMargin=24 * mm, leftMargin=24 * mm, topMargin=22 * mm, bottomMargin=20 * mm,
        title=case_title, author=court_name,
    )
    story = [
        Paragraph(court_name.upper(), styles["CourtHeader"]),
        Paragraph("IN THE HIGH COURT OF JUDICATURE", styles["CourtHeader"]),
        Paragraph(case_title, styles["CaseTitle"]),
        Spacer(1, 8 * mm),
        Paragraph(f"Date of decision: {decision_date}", styles["JudgmentBody"]),
        Paragraph("JUDGMENT", styles["CourtHeader"]),
        Paragraph(
            "The matter was heard upon the pleadings, the material placed on record, "
            "and submissions advanced by learned counsel for the parties.",
            styles["JudgmentBody"],
        ),
        PageBreak(),
    ]
    for index, text in enumerate(paragraphs, start=1):
        story.append(Paragraph(f"<b>{index}.</b> {text}", styles["JudgmentBody"]))
    story.extend([
        Paragraph(
            "For the reasons recorded above, the petition is disposed of in accordance with law. "
            "There shall be no order as to costs.",
            styles["JudgmentBody"],
        ),
        PageBreak(),
        Paragraph("APPENDIX — RECORD OF PROCEEDINGS", styles["CourtHeader"]),
        Paragraph(
            "This synthetic judgment is generated for BenchSplit demonstration and testing. "
            "It is not an authentic judicial decision and must not be cited as legal authority.",
            styles["JudgmentBody"],
        ),
    ])
    def draw_page_footer(canvas, _document) -> None:
        canvas.saveState()
        canvas.setFont("Times-Italic", 7)
        canvas.setFillColor(colors.grey)
        canvas.drawString(
            24 * mm, 12 * mm,
            "BENCHSPLIT SYNTHETIC DEMO - NOT AN AUTHENTIC JUDGMENT",
        )
        canvas.drawRightString(A4[0] - 24 * mm, 12 * mm, f"Page {_document.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=draw_page_footer, onLaterPages=draw_page_footer)
    return path


def _rectangles_for_offsets(page, char_start: int, char_end: int, scale_x: float, scale_y: float) -> list[tuple[float, float, float, float]]:
    page_text = page.extract_text(layout=False) or ""
    normalized_text, original_offsets = normalize_with_index(page_text)
    relevant: list[tuple[float, float, float, float]] = []
    cursor = 0
    for word in page.extract_words(x_tolerance=2, y_tolerance=3, keep_blank_chars=False, use_text_flow=True, extra_attrs=["fontname"]):
        normalized_word, _ = normalize_with_index(word["text"])
        if not normalized_word:
            continue
        position = normalized_text.find(normalized_word, cursor)
        if position < 0:
            position = normalized_text.find(normalized_word)
        if position < 0:
            continue
        cursor = position + len(normalized_word)
        first = original_offsets[position]
        last = original_offsets[min(position + len(normalized_word) - 1, len(original_offsets) - 1)] + 1
        if first < char_end and last > char_start:
            relevant.append((
                float(word["x0"]) * scale_x,
                float(word["top"]) * scale_y,
                float(word["x1"]) * scale_x,
                float(word["bottom"]) * scale_y,
            ))
    return relevant


def render_highlighted_page(
    pdf_path: str | Path,
    page_number: int,
    char_start: int,
    char_end: int,
    output_path: Optional[str | Path] = None,
) -> Path:
    pdf_path = Path(pdf_path)
    output = Path(output_path) if output_path else PAGE_CACHE_DIR / f"{pdf_path.stem}-p{page_number}-{char_start}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    pdf_document = pdfium.PdfDocument(str(pdf_path))
    try:
        if page_number < 1 or page_number > len(pdf_document):
            raise ValueError(f"Page {page_number} is outside the PDF page range")
        pdf_page = pdf_document[page_number - 1]
        bitmap = pdf_page.render(scale=2.0)
        image = bitmap.to_pil().convert("RGBA")
        page_width, page_height = float(pdf_page.get_width()), float(pdf_page.get_height())
    finally:
        pdf_document.close()
    with pdfplumber.open(str(pdf_path)) as document:
        text_page = document.pages[page_number - 1]
        sx, sy = image.width / page_width, image.height / page_height
        rectangles = _rectangles_for_offsets(text_page, char_start, char_end, sx, sy)
    if not rectangles:
        page_text = extract_pdf_pages(pdf_path)[page_number - 1]
        if char_start < 0 or char_end > len(page_text) or char_end <= char_start:
            raise ValueError("Quote offsets do not fall within the selected PDF page")
    draw = ImageDraw.Draw(image, "RGBA")
    for left, top, right, bottom in rectangles:
        draw.rectangle(
            (left - 2, top - 1, right + 2, bottom + 1),
            fill=(250, 204, 21, 95),
            outline=(220, 38, 38, 220),
            width=2,
        )
    image.save(output, format="PNG")
    return output
