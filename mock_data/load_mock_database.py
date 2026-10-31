"""Add the clearly marked fabricated corpus to the configured local database."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from backend.config import DATABASE_PATH

ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT.parent / "backend" / "schema.sql"
JSONL_PATH = ROOT / "data" / "processed" / "benchsplit_dataset.jsonl"


def load_demo_data(database_path: Path = DATABASE_PATH) -> tuple[int, int]:
    records = [json.loads(line) for line in JSONL_PATH.read_text(encoding="utf-8").splitlines()]
    expected = json.loads((ROOT / "expected_conflicts.json").read_text(encoding="utf-8"))
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    courts = {
        record["court_id"]: (
            record["court_id"],
            record["court"],
            record["court_id"].replace("_", " "),
            record.get("level", "SC" if record["court_id"] == "SCI" else "HC"),
        )
        for record in records
    }
    connection.executemany(
        "INSERT OR IGNORE INTO courts (id, name, short_code, level) VALUES (?, ?, ?, ?)",
        courts.values(),
    )

    proposition_ids = {}
    for record in records:
        judgment_id = f"FAKE-J-{record['document_id']}"
        proposition_id = f"FAKE-P-{record['document_id']}"
        proposition_ids[record["document_id"]] = proposition_id
        metadata_path = ROOT / "data" / "metadata" / f"{record['document_id']}.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        text_path = ROOT / "data" / "extracted_text" / f"{record['document_id']}.txt"
        text = text_path.read_text(encoding="utf-8")
        connection.execute(
            """INSERT INTO judgments
               (id, court_id, cnr, title, decision_date, s3_uri, local_pdf_path,
                pdf_sha256, has_text_layer, n_pages)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 1)
               ON CONFLICT(id) DO NOTHING""",
            (
                judgment_id,
                record["court_id"],
                record["case_number"],
                record.get("title", metadata["title"]),
                record["decision_date"],
                record["source_uri"],
                str(text_path),
                hashlib.sha256(text.encode("utf-8")).hexdigest(),
            ),
        )
        quote = record["decision_evidence"]
        connection.execute(
            """INSERT INTO propositions
               (id, judgment_id, statute_key, question, holding, quote, page,
                char_start, char_end, verify_status, verify_score, retry_count,
                entailment_supported, model_name, prompt_version)
               VALUES (?, ?, 'NI_ACT_S138', ?, ?, ?, 1, ?, ?, 'VERIFIED_EXACT',
                       100.0, 0, 1, 'fake-test-fixture', 'fake-v1')
               ON CONFLICT(id) DO NOTHING""",
            (
                proposition_id,
                judgment_id,
                record["question"],
                record["holding"],
                quote,
                text.index(quote),
                text.index(quote) + len(quote),
            ),
        )

    cluster_id = "FAKE-CLUSTER-NI-ACT-S138"
    connection.execute(
        """INSERT OR IGNORE INTO clusters
           (id, statute_key, canonical_question, method, threshold) VALUES (?, ?, ?, ?, ?)""",
        (cluster_id, "NI_ACT_S138", "Does dispatch alone satisfy Section 138 notice service?", "fake_expected_fixture", 1.0),
    )
    for proposition_id in proposition_ids.values():
        connection.execute(
            "INSERT OR IGNORE INTO cluster_members (cluster_id, proposition_id) VALUES (?, ?)",
            (cluster_id, proposition_id),
        )

    inserted_edges = 0
    for index, pair in enumerate(expected, start=1):
        supreme_court_id = proposition_ids["FAKE-SC-138-001"]
        cursor = connection.execute(
            """INSERT OR IGNORE INTO pair_labels
               (id, statute_key, cluster_id, prop_a_id, prop_b_id, candidate_score,
                label, reason, votes_json, confidence, sc_status, sc_prop_id)
               VALUES (?, ?, ?, ?, ?, ?, 'CONFLICT', ?, ?, ?, ?, ?)""",
            (
                f"FAKE-LABEL-{index}",
                pair["statute_key"],
                cluster_id,
                proposition_ids[pair["prop_a"]],
                proposition_ids[pair["prop_b"]],
                1.0,
                "FAKE TEST DATA ONLY. " + pair["reason"],
                json.dumps(["CONFLICT", "CONFLICT", "CONFLICT"]),
                1.0,
                "Supreme Court fixture proposition found; all records are fabricated test data.",
                supreme_court_id,
            ),
        )
        inserted_edges += cursor.rowcount
    connection.commit()
    connection.close()
    return len(records), inserted_edges


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=DATABASE_PATH,
        help=f"SQLite database to add demo records to (default: {DATABASE_PATH})",
    )
    args = parser.parse_args()
    records, edges = load_demo_data(args.database)
    print(f"Processed {records} fabricated judgment fixtures in {args.database} (safe to rerun)")
    print(f"Added {edges} fabricated High-Court conflict edges with an SC fixture reference")


if __name__ == "__main__":
    main()
