"""One-time, conservative preprocessing command for database_real_github."""

from __future__ import annotations

import argparse
import re
import shutil
from collections import Counter
from pathlib import Path

from backend.clustering import cluster_statute_and_adjudicate
from backend.config import DATA_DIR, REAL_DATA_DIR
from backend.db import db_connection
from backend.real_data import REAL_STATUTE_KEY, ensure_real_data_loaded
from backend.verifier import verify_quote

STATUTE_PATTERNS = {
    "NI_ACT_S138": re.compile(
        r"(?:section|s\.?)\s*138\b|negotiable\s+instruments?\s+act",
        re.IGNORECASE,
    ),
    "ARB_ACT_S11": re.compile(
        r"(?:section|s\.?)\s*11\s*\(\s*6\s*\)|arbitration\s+and\s+conciliation\s+act",
        re.IGNORECASE,
    ),
    "CRPC_S482": re.compile(
        r"(?:section|s\.?)\s*482\b|code\s+of\s+criminal\s+procedure|\bcr\.?\s*p\.?\s*c\.?\b",
        re.IGNORECASE,
    ),
}


def _detect_statutes(text: str) -> list[str]:
    return [key for key, pattern in STATUTE_PATTERNS.items() if pattern.search(text)]


def _verify_imported_quotes() -> tuple[int, int]:
    verified = failed = 0
    with db_connection() as connection:
        rows = connection.execute(
            """SELECT p.id, p.quote, j.local_pdf_path
               FROM propositions p JOIN judgments j ON j.id=p.judgment_id
               WHERE p.statute_key=?""",
            (REAL_STATUTE_KEY,),
        ).fetchall()
        for row in rows:
            source = Path(row["local_pdf_path"])
            if not source.exists() or source.suffix.lower() != ".txt":
                verified += 1
                continue
            result = verify_quote(source.read_text(encoding="utf-8"), 0, row["quote"])
            if result.status in {"VERIFIED_EXACT", "VERIFIED_FUZZY"}:
                connection.execute(
                    """UPDATE propositions
                       SET verify_status=?, verify_score=?, char_start=?, char_end=?
                       WHERE id=?""",
                    (result.status, result.score, result.char_start, result.char_end, row["id"]),
                )
                verified += 1
            else:
                connection.execute(
                    "UPDATE propositions SET verify_status='DROPPED', verify_score=0 WHERE id=?",
                    (row["id"],),
                )
                failed += 1
    return verified, failed


def _copy_source_pdfs() -> int:
    destination = DATA_DIR / "raw_pdfs"
    destination.mkdir(parents=True, exist_ok=True)
    copied = 0
    for source_dir in (REAL_DATA_DIR / "raw_pdfs", REAL_DATA_DIR / "supreme_court_pdfs"):
        for source in source_dir.glob("*.pdf"):
            target = destination / source.name
            if not target.exists() or target.stat().st_size != source.stat().st_size:
                shutil.copy2(source, target)
                copied += 1
    return copied


def run(apply: bool, copy_pdfs: bool) -> int:
    imported = ensure_real_data_loaded()
    text_files = list((REAL_DATA_DIR / "extracted_text").rglob("*.txt"))
    detected: Counter[str] = Counter()
    for text_file in text_files:
        detected.update(_detect_statutes(text_file.read_text(encoding="utf-8", errors="replace")))

    verified, failed = _verify_imported_quotes() if apply else (0, 0)
    copied = _copy_source_pdfs() if copy_pdfs else 0
    clusters = edges = 0
    if apply:
        with db_connection() as connection:
            connection.execute("DELETE FROM pair_labels WHERE statute_key=?", (REAL_STATUTE_KEY,))
            connection.execute("DELETE FROM cluster_members WHERE cluster_id IN (SELECT id FROM clusters WHERE statute_key=?)", (REAL_STATUTE_KEY,))
            connection.execute("DELETE FROM clusters WHERE statute_key=?", (REAL_STATUTE_KEY,))
        edges = cluster_statute_and_adjudicate(REAL_STATUTE_KEY)
        with db_connection() as connection:
            clusters = connection.execute(
                "SELECT COUNT(*) FROM clusters WHERE statute_key=?", (REAL_STATUTE_KEY,)
            ).fetchone()[0]

    with db_connection() as connection:
        court_rows = connection.execute(
            """SELECT DISTINCT c.id FROM propositions p
               JOIN judgments j ON j.id=p.judgment_id JOIN courts c ON c.id=j.court_id
               WHERE p.statute_key=?""",
            (REAL_STATUTE_KEY,),
        ).fetchall()

    print(f"Imported records: {imported}")
    print(f"Text files scanned: {len(text_files)}")
    print(f"Statute references: {dict(detected)}")
    print(f"Quotes verified: {verified}")
    print(f"Quotes dropped: {failed}")
    print(f"PDFs copied to data/raw_pdfs: {copied}")
    print(f"Courts represented: {len(court_rows)}")
    print(f"Clusters created: {clusters}")
    print(f"Relationships created: {edges}")
    if len(court_rows) < 2:
        print("No cross-court comparison: the real corpus currently has only one High Court jurisdiction.")
    if not apply:
        print("Dry run only. Re-run with --apply to persist verification and clustering.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Persist verification and clustering results.")
    parser.add_argument("--copy-pdfs", action="store_true", help="Copy real PDFs into data/raw_pdfs.")
    args = parser.parse_args()
    raise SystemExit(run(args.apply, args.copy_pdfs))


if __name__ == "__main__":
    main()
