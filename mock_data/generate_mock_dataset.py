"""Generate a clearly marked fabricated corpus for local UI and pipeline tests."""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
TEXT_DIR = DATA / "extracted_text"
META_DIR = DATA / "metadata"
PROCESSED_DIR = DATA / "processed"

CASES = [
    {
        "id": "FAKE-BOMBAY-138-001",
        "court": "IN THE HIGH COURT OF JUDICATURE AT BOMBAY",
        "court_id": "BOMBAY_HC",
        "short_code": "BOMBAY HC",
        "level": "HC",
        "case_number": "FAKE-CRL-001/2026",
        "date": "2026-01-15",
        "title": "FAKE TEST: Meridian Traders v. State",
        "holding": "A complaint under Section 138 may proceed when the statutory notice is dispatched to the last known address, even if delivery is not proved.",
        "quote": "FAKE HOLDING: Dispatch to the last known address is sufficient for Section 138 notice compliance; proof of actual delivery is unnecessary.",
        "side": "DISPATCH_SUFFICIENT",
    },
    {
        "id": "FAKE-DELHI-138-001",
        "court": "IN THE HIGH COURT OF DELHI",
        "court_id": "DELHI_HC",
        "short_code": "DELHI HC",
        "level": "HC",
        "case_number": "FAKE-CRL-002/2026",
        "date": "2026-02-10",
        "title": "FAKE TEST: Northstar Exports v. State",
        "holding": "A complaint under Section 138 cannot proceed unless actual delivery of the statutory notice is proved.",
        "quote": "FAKE HOLDING: Dispatch alone is insufficient for Section 138 notice compliance; actual delivery must be proved before the complaint proceeds.",
        "side": "DELIVERY_REQUIRED",
    },
    {
        "id": "FAKE-BENGALURU-138-001",
        "court": "IN THE HIGH COURT OF KARNATAKA AT BENGALURU",
        "court_id": "KARNATAKA_HC",
        "short_code": "KARNATAKA HC",
        "level": "HC",
        "case_number": "FAKE-CRL-003/2026",
        "date": "2026-03-05",
        "title": "FAKE TEST: Riverstone Systems v. State",
        "holding": "A complaint under Section 138 may proceed when the statutory notice is dispatched to the last known address, even if delivery is not proved.",
        "quote": "FAKE HOLDING: For Section 138, dispatch to the last known address completes notice compliance even without proof of actual delivery.",
        "side": "DISPATCH_SUFFICIENT",
    },
    {
        "id": "FAKE-SC-138-001",
        "court": "IN THE SUPREME COURT OF INDIA",
        "court_id": "SCI",
        "short_code": "SCI",
        "level": "SC",
        "case_number": "FAKE-CIV-004/2026",
        "date": "2026-04-20",
        "title": "FAKE TEST: Apex Reference on Notice",
        "holding": "A complaint under Section 138 requires proof that the statutory notice reached the drawer or was deliberately avoided.",
        "quote": "FAKE HOLDING: Section 138 notice compliance requires proof of receipt or deliberate avoidance; dispatch by itself does not complete service.",
        "side": "DELIVERY_REQUIRED",
    },
]


def main() -> None:
    for directory in (TEXT_DIR, META_DIR, PROCESSED_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    records = []
    expected = []
    for case in CASES:
        text = (
            f"FAKE TEST DATA ONLY. This is fabricated text and is not a real judgment.\n\n"
            f"{case['court']}\n{case['title']}\nCase No. {case['case_number']}\n"
            f"Decision date: {case['date']}\n\n"
            "Question: Does dispatch of a Section 138 notice to the last known address "
            "satisfy the notice requirement without proof of actual delivery?\n\n"
            f"{case['quote']}\n\n{case['holding']}\n"
        )
        (TEXT_DIR / f"{case['id']}.txt").write_text(text, encoding="utf-8")
        (META_DIR / f"{case['id']}.json").write_text(
            json.dumps(
                {
                    "fake_test_data": True,
                    "document_id": case["id"],
                    "court": case["court"],
                    "court_id": case["court_id"],
                    "level": case["level"],
                    "title": case["title"],
                    "case_number": case["case_number"],
                    "decision_date": case["date"],
                    "title": case["title"],
                    "statute_key": "NI_ACT_S138",
                    "question": "Does dispatch alone satisfy Section 138 notice service?",
                    "holding": case["holding"],
                    "source_uri": f"fake://FAKE_TEST_DATA/{case['id']}.txt",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        records.append(
            {
                "fake_test_data": True,
                "document_id": case["id"],
                "court": case["court"],
                "court_id": case["court_id"],
                "case_number": case["case_number"],
                "decision_date": case["date"],
                "statute_key": "NI_ACT_S138",
                "question": "Does dispatch alone satisfy Section 138 notice service?",
                "holding": case["holding"],
                "decision_evidence": case["quote"],
                "judgment_text": text,
                "source_uri": f"fake://FAKE_TEST_DATA/{case['id']}.txt",
            }
        )

    (PROCESSED_DIR / "benchsplit_dataset.jsonl").write_text(
        "\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8"
    )
    with (PROCESSED_DIR / "benchsplit_dataset.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["fake_test_data", "document_id", "court_id", "case_number", "decision_date", "statute_key", "question", "holding", "source_uri"],
        )
        writer.writeheader()
        writer.writerows({key: record[key] for key in writer.fieldnames} for record in records)

    for first in CASES:
        for second in CASES:
            if (
                first["id"] >= second["id"]
                or first["level"] != "HC"
                or second["level"] != "HC"
                or first["side"] == second["side"]
            ):
                continue
            expected.append(
                {
                    "fake_test_data": True,
                    "statute_key": "NI_ACT_S138",
                    "prop_a": first["id"],
                    "prop_b": second["id"],
                    "label": "CONFLICT",
                    "reason": "Fabricated holdings intentionally state opposite answers to the same fabricated question.",
                }
            )
    (ROOT / "expected_conflicts.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(records)} fabricated records and {len(expected)} expected conflicts.")


if __name__ == "__main__":
    main()
