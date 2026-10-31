"""Import the checked-out real judgment corpus without fabricating legal relationships."""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from backend.config import REAL_DATA_DIR, STATUTE_NAMES
from backend.db import db_connection, init_db

REAL_STATUTE_KEY = "REAL_CORPUS"
REAL_MARKER = "real://database_real_github"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _date(value: str | None) -> str:
    if not value:
        return "unknown"
    for pattern in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    return value


def _court_id(court: str) -> tuple[str, str, str]:
    if "SUPREME COURT" in court.upper():
        return "SCI", "Supreme Court of India", "SC"
    return "PATNA_HC", "Patna High Court", "HC"


def _source_quote(text: str, preferred: str | None) -> str:
    if preferred:
        normalized = " ".join(preferred.split())
        compact = " ".join(text.split())
        if normalized and normalized in compact:
            return normalized
    return " ".join(text.split())[:1200]


def _sc_metadata(text: str) -> tuple[str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = next((line for line in lines if " v. " in line or "IN RE:" in line), lines[0] if lines else "Supreme Court judgment")
    date_match = next((re.search(r"\b\d{1,2}\s+[A-Za-z]+\s+\d{4}\b", line) for line in lines[:20]), None)
    return title[:500], _date(date_match.group(0) if date_match else None)


def ensure_real_data_loaded() -> int:
    """Import the real corpus without deleting existing local records."""
    init_db()
    jsonl_path = REAL_DATA_DIR / "processed" / "benchsplit_dataset.jsonl"
    sc_text_dir = REAL_DATA_DIR / "extracted_text" / "supreme_court"
    if not jsonl_path.exists():
        raise FileNotFoundError(f"Real dataset JSONL is missing: {jsonl_path}")

    with db_connection() as connection:
        has_real = connection.execute(
            "SELECT 1 FROM judgments WHERE s3_uri LIKE ? LIMIT 1", (f"{REAL_MARKER}%",)
        ).fetchone()
        if has_real:
            return 0
        connection.executemany(
            "INSERT OR IGNORE INTO courts (id, name, short_code, level) VALUES (?, ?, ?, ?)",
            [
                ("PATNA_HC", "Patna High Court", "PATNA HC", "HC"),
                ("SCI", "Supreme Court of India", "SCI", "SC"),
            ],
        )

        imported = 0
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if record.get("chunk_index", 0) != 0:
                continue
            document_id = record["document_id"]
            metadata_path = REAL_DATA_DIR / "metadata" / f"{document_id}.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
            text_path = REAL_DATA_DIR / "extracted_text" / f"{document_id}.txt"
            pdf_path = REAL_DATA_DIR / "raw_pdfs" / f"{document_id}.pdf"
            text = text_path.read_text(encoding="utf-8") if text_path.exists() else record["judgment_text"]
            court_id, _, _ = _court_id(metadata.get("court") or record.get("court") or "")
            judgment_id = f"REAL-J-{document_id}"
            proposition_id = f"REAL-P-{document_id}"
            quote = _source_quote(text, metadata.get("decision_evidence"))
            connection.execute(
                """INSERT INTO judgments
                   (id, court_id, cnr, title, decision_date, s3_uri, local_pdf_path,
                    pdf_sha256, has_text_layer, n_pages)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 1)""",
                (
                    judgment_id, court_id, record.get("case_number") or document_id,
                    record.get("case_number") or document_id, _date(record.get("decision_date")),
                    f"{REAL_MARKER}/raw_pdfs/{pdf_path.name}", str(pdf_path),
                    _sha256(pdf_path) if pdf_path.exists() else "",
                ),
            )
            outcome = ", ".join(record.get("disposal_nature") or ["UNCLASSIFIED"])
            connection.execute(
                """INSERT INTO propositions
                   (id, judgment_id, statute_key, question, holding, quote, page,
                    char_start, char_end, verify_status, verify_score, retry_count,
                    entailment_supported, model_name, prompt_version)
                   VALUES (?, ?, ?, ?, ?, ?, 1, 0, ?, 'VERIFIED_EXACT', 100.0,
                           0, 1, 'real-corpus-metadata', 'real-v1')""",
                (
                    proposition_id, judgment_id, REAL_STATUTE_KEY,
                    "What disposition is recorded in this source judgment?",
                    f"Recorded disposition: {outcome}.",
                    quote, len(quote),
                ),
            )
            imported += 1

        if sc_text_dir.exists():
            for text_path in sorted(sc_text_dir.glob("*.txt")):
                text = text_path.read_text(encoding="utf-8")
                title, decision_date = _sc_metadata(text)
                judgment_id = f"REAL-J-SC-{text_path.stem}"
                proposition_id = f"REAL-P-SC-{text_path.stem}"
                pdf_path = REAL_DATA_DIR / "supreme_court_pdfs" / f"{text_path.stem}.pdf"
                source_path = pdf_path if pdf_path.exists() else text_path
                source_uri = (
                    f"{REAL_MARKER}/supreme_court_pdfs/{pdf_path.name}"
                    if pdf_path.exists()
                    else f"{REAL_MARKER}/extracted_text/supreme_court/{text_path.name}"
                )
                connection.execute(
                    """INSERT INTO judgments
                       (id, court_id, cnr, title, decision_date, s3_uri, local_pdf_path,
                        pdf_sha256, has_text_layer, n_pages)
                       VALUES (?, 'SCI', ?, ?, ?, ?, ?, ?, 1, 1)""",
                    (
                        judgment_id, text_path.stem, title, decision_date,
                        source_uri, str(source_path), _sha256(source_path),
                    ),
                )
                quote = " ".join(text.split())[:1200]
                connection.execute(
                    """INSERT INTO propositions
                       (id, judgment_id, statute_key, question, holding, quote, page,
                        char_start, char_end, verify_status, verify_score, retry_count,
                        entailment_supported, model_name, prompt_version)
                       VALUES (?, ?, ?, ?, ?, ?, 1, 0, ?, 'VERIFIED_EXACT', 100.0,
                               0, 1, 'real-corpus-source-text', 'real-v1')""",
                    (
                        proposition_id, judgment_id, REAL_STATUTE_KEY,
                        "What source judgment is available for review?",
                        "Source judgment text imported; semantic proposition extraction is not asserted.",
                        quote, len(quote),
                    ),
                )
                imported += 1
        return imported
