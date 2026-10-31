from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from backend.config import BRIEFS_DIR, STATUTE_NAMES
from backend.db import db_connection


def generate_forum_risk_brief(statute_key: str, output_path: str | Path | None = None) -> Path:
    if statute_key not in STATUTE_NAMES:
        raise ValueError(f"Unsupported statute key: {statute_key}")
    path = Path(output_path) if output_path else BRIEFS_DIR / f"{statute_key}.pdf"
    with db_connection() as connection:
        conflicts = connection.execute(
            """SELECT pl.label, pl.reason, pl.confidence, pl.sc_status, pa.question,
                      pa.holding AS holding_a, pb.holding AS holding_b,
                      ca.name AS court_a, cb.name AS court_b
               FROM pair_labels pl JOIN propositions pa ON pa.id=pl.prop_a_id
               JOIN propositions pb ON pb.id=pl.prop_b_id
               JOIN judgments ja ON ja.id=pa.judgment_id JOIN courts ca ON ca.id=ja.court_id
               JOIN judgments jb ON jb.id=pb.judgment_id JOIN courts cb ON cb.id=jb.court_id
               WHERE pl.statute_key=? AND pl.label='CONFLICT'
               ORDER BY pl.confidence DESC LIMIT 3""",
            (statute_key,),
        ).fetchall()
        verified_count = connection.execute(
            "SELECT COUNT(*) FROM propositions WHERE statute_key=? AND verify_status IN ('VERIFIED_EXACT','VERIFIED_FUZZY')",
            (statute_key,),
        ).fetchone()[0]
        conflict_count = connection.execute(
            "SELECT COUNT(*) FROM pair_labels WHERE statute_key=? AND label='CONFLICT'",
            (statute_key,),
        ).fetchone()[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("BriefTitle", parent=styles["Title"], alignment=TA_CENTER, fontSize=15, leading=19)
    small = ParagraphStyle("BriefBody", parent=styles["BodyText"], fontSize=7.5, leading=9)
    story = [
        Paragraph("FORUM-RISK BRIEF", title),
        Paragraph(escape(STATUTE_NAMES[statute_key]), styles["Heading2"]),
        Paragraph(
            "Research screening summary only. This synthetic/demo analysis is not legal advice; "
            "all cited decisions and propositions require independent counsel verification.",
            small,
        ),
        Spacer(1, 5 * mm),
        Paragraph(f"Verified propositions reviewed: {verified_count}", styles["BodyText"]),
        Paragraph(
            f"Potential conflicts detected: {conflict_count}; examples shown: {len(conflicts)}",
            styles["BodyText"],
        ),
        Spacer(1, 3 * mm),
    ]
    for index, row in enumerate(conflicts, start=1):
        story.append(Paragraph(f"<b>{index}. {escape(row['question'])}</b>", small))
        story.append(Paragraph(
            f"{escape(row['court_a'])}: {escape(row['holding_a'])}<br/>"
            f"{escape(row['court_b'])}: {escape(row['holding_b'])}<br/>"
            f"Assessment ({row['confidence']:.0%} confidence): {escape(row['reason'])}<br/>"
            f"Supreme Court scan: {escape(row['sc_status'])}",
            small,
        ))
        story.append(Spacer(1, 2 * mm))
    if not conflicts:
        story.append(Paragraph("No adjudicated conflict pair is currently recorded for this provision.", small))
    story.extend([
        Spacer(1, 4 * mm),
        Paragraph(
            "Conflict definition: a material, irreconcilable difference in legal rule on the same "
            "statutory provision and materially similar question.",
            small,
        ),
    ])
    document = SimpleDocTemplate(
        str(path), pagesize=A4, rightMargin=12 * mm, leftMargin=12 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
    )
    document.build(story)
    return path
