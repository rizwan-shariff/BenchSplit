"""Create a separate real-plus-fake database for UI relationship testing.

The inserted edge labels are fixture labels, not conclusions about the real
Patna judgments. The real database is copied and never modified.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

from generate_mock_dataset import CASES, main as generate_mock_dataset

ROOT = Path(__file__).resolve().parent
REAL_DB = ROOT.parent / "data" / "benchsplit.db"
MIXED_DB = ROOT / "mixed_real_fake_test.db"
SCHEMA = ROOT.parent / "backend" / "schema.sql"


def main() -> None:
    generate_mock_dataset()
    if not REAL_DB.exists():
        raise FileNotFoundError(f"Real database is missing: {REAL_DB}")
    shutil.copy2(REAL_DB, MIXED_DB)
    connection = sqlite3.connect(MIXED_DB)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA.read_text(encoding="utf-8"))

    connection.executemany(
        "INSERT OR IGNORE INTO courts (id, name, short_code, level) VALUES (?, ?, ?, ?)",
        [
            ("BOMBAY_HC", "Bombay High Court", "BOMBAY HC", "HC"),
            ("DELHI_HC", "Delhi High Court", "DELHI HC", "HC"),
            ("KARNATAKA_HC", "Karnataka High Court at Bengaluru", "KARNATAKA HC", "HC"),
        ],
    )
    fake_ids: dict[str, str] = {}
    for case in CASES:
        judgment_id = f"FAKE-MIXED-J-{case['id']}"
        proposition_id = f"FAKE-MIXED-P-{case['id']}"
        fake_ids[case["id"]] = proposition_id
        text_path = ROOT / "data" / "extracted_text" / f"{case['id']}.txt"
        text = text_path.read_text(encoding="utf-8")
        connection.execute(
            """INSERT OR REPLACE INTO judgments
               (id, court_id, cnr, title, decision_date, s3_uri, local_pdf_path,
                pdf_sha256, has_text_layer, n_pages)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 1)""",
            (
                judgment_id,
                case["court_id"],
                case["case_number"],
                case["title"],
                case["date"],
                f"fake://FAKE_TEST_DATA/{case['id']}.txt",
                str(text_path),
                hashlib.sha256(text.encode("utf-8")).hexdigest(),
            ),
        )
        quote = case["quote"]
        connection.execute(
            """INSERT OR REPLACE INTO propositions
               (id, judgment_id, statute_key, question, holding, quote, page,
                char_start, char_end, verify_status, verify_score, retry_count,
                entailment_supported, model_name, prompt_version)
               VALUES (?, ?, 'REAL_CORPUS', ?, ?, ?, 1, ?, ?, 'VERIFIED_EXACT',
                       100.0, 0, 1, 'fake-mixed-fixture', 'fake-mixed-v1')""",
            (
                proposition_id,
                judgment_id,
                "Fixture comparison only: " + "Does the recorded source support the tested relationship?",
                case["holding"],
                quote,
                text.index(quote),
                text.index(quote) + len(quote),
            ),
        )

    patna = [
        row[0]
        for row in connection.execute(
            """SELECT p.id FROM propositions p JOIN judgments j ON j.id=p.judgment_id
               WHERE p.statute_key='REAL_CORPUS' AND j.court_id='PATNA_HC'
               ORDER BY j.id LIMIT 4"""
        ).fetchall()
    ]
    if len(patna) < 4:
        raise RuntimeError("The real database must contain at least four Patna propositions.")

    cluster_id = "FAKE-MIXED-CLUSTER-REAL-CORPUS"
    connection.execute(
        """INSERT OR REPLACE INTO clusters
           (id, statute_key, canonical_question, method, threshold)
           VALUES (?, 'REAL_CORPUS', ?, 'fake_mixed_fixture', 1.0)""",
        (cluster_id, "Fixture comparison against imported Patna source records"),
    )
    for proposition_id in (*patna, *(fake_ids.values())):
        connection.execute(
            "INSERT OR IGNORE INTO cluster_members (cluster_id, proposition_id) VALUES (?, ?)",
            (cluster_id, proposition_id),
        )

    fixture_pairs = [
        ("FAKE-BOMBAY-138-001", patna[0], "AGREE", "Both holdings are treated as compatible for this fixture because they allow the notice-related application to proceed on the stated record."),
        ("FAKE-DELHI-138-001", patna[1], "DISTINGUISHABLE_ON_FACTS", "The outcomes are not compared as opposite rules because the fabricated Delhi record relies on actual-delivery facts while the Patna record concerns a different procedural setting."),
        ("FAKE-BENGALURU-138-001", patna[2], "CONFLICT", "The fabricated Bengaluru holding permits the complaint without delivery proof, while the selected Patna holding is intentionally treated as requiring the opposite notice-service approach."),
        ("FAKE-SC-138-001", patna[3], "AGREE", "Both holdings are treated as aligned for this fixture because each supports proceeding where the notice requirement is satisfied on the recorded facts."),
    ]
    for index, (fake_id, real_id, label, reason) in enumerate(fixture_pairs, start=1):
        connection.execute(
            """INSERT OR REPLACE INTO pair_labels
               (id, statute_key, cluster_id, prop_a_id, prop_b_id, candidate_score,
                label, reason, votes_json, confidence, sc_status, sc_prop_id)
               VALUES (?, 'REAL_CORPUS', ?, ?, ?, 1.0, ?, ?, ?, 1.0,
                       'FAKE_TEST_DATA', NULL)""",
            (
                f"FAKE-MIXED-LABEL-{index}",
                cluster_id,
                fake_ids[fake_id],
                real_id,
                label,
                f"FAKE_TEST_DATA fixture label: {reason} This is not a legal conclusion.",
                json.dumps([label, label, label]),
            ),
        )
    connection.commit()
    connection.close()
    print(f"Created separate mixed database: {MIXED_DB}")
    print("Retained real Patna/Supreme Court records and added four fake fixture propositions.")
    print("Inserted fixture labels: 1 CONFLICT, 2 AGREE, 1 DISTINGUISHABLE_ON_FACTS.")


if __name__ == "__main__":
    main()
