"""Replace the local demo database with the supplied synthetic PDF corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

from backend.config import DATABASE_PATH, RAW_PDFS_DIR
from backend.pdf_processor import extract_pdf_pages, sha256_file
from backend.verifier import verify_quote

ROOT = Path(__file__).resolve().parent / "benchsplit_synthetic_corpus"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "backend" / "schema.sql"


def _id(prefix: str, value: str) -> str:
    return f"{prefix}-SAMPLE-{value}"


def load_sample_database(
    database_path: Path = DATABASE_PATH,
    raw_pdfs_dir: Path = RAW_PDFS_DIR,
    corpus_root: Path = ROOT,
) -> tuple[int, int, int]:
    manifest = json.loads((corpus_root / "manifest.json").read_text(encoding="utf-8"))
    raw_pdfs_dir.mkdir(parents=True, exist_ok=True)
    for existing in raw_pdfs_dir.iterdir():
        if existing.is_file():
            existing.unlink()
    for record in manifest["judgments"]:
        source = corpus_root / record["file"]
        shutil.copy2(source, raw_pdfs_dir / source.name)

    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    for table in (
        "gold_pairs",
        "pair_labels",
        "cluster_members",
        "clusters",
        "propositions",
        "judgments",
        "courts",
    ):
        connection.execute(f"DELETE FROM {table}")

    courts = {
        record["court_id"]: (
            record["court_id"],
            record["court_name"],
            record["court_id"],
            record["level"],
        )
        for record in manifest["judgments"]
    }
    connection.executemany(
        "INSERT INTO courts (id, name, short_code, level) VALUES (?, ?, ?, ?)",
        courts.values(),
    )

    proposition_ids: dict[str, str] = {}
    for record in manifest["judgments"]:
        source = corpus_root / record["file"]
        destination = raw_pdfs_dir / source.name
        pages = extract_pdf_pages(source)
        page_index = record["quote_page"] - 1
        if page_index < 0 or page_index >= len(pages):
            raise ValueError(f"{record['id']} quote page is outside the PDF")
        verification = verify_quote(pages[page_index], 0, record["quote"])
        if verification.status not in {"VERIFIED_EXACT", "VERIFIED_FUZZY"}:
            raise ValueError(f"Quote could not be verified for {record['id']}")

        judgment_id = _id("J", record["id"])
        proposition_id = _id("P", record["id"])
        proposition_ids[record["id"]] = proposition_id
        connection.execute(
            """INSERT INTO judgments
               (id, court_id, cnr, title, decision_date, s3_uri, local_pdf_path,
                pdf_sha256, has_text_layer, n_pages)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                judgment_id,
                record["court_id"],
                record["cnr"],
                record["title"],
                record["decision_date"],
                f"demo://synthetic/{destination.name}",
                str(destination),
                sha256_file(destination),
                record.get("has_text_layer", 1),
                record["n_pages"],
            ),
        )
        connection.execute(
            """INSERT INTO propositions
               (id, judgment_id, statute_key, question, holding, quote, page,
                char_start, char_end, verify_status, verify_score, retry_count,
                entailment_supported, model_name, prompt_version)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1, ?, ?)""",
            (
                proposition_id,
                judgment_id,
                record["statute_key"],
                record["question"],
                record["holding"],
                verification.quote,
                record["quote_page"],
                verification.char_start,
                verification.char_end,
                verification.status,
                verification.score,
                "sample-manifest",
                "sample-v1",
            ),
        )

    for cluster in manifest["clusters"]:
        connection.execute(
            """INSERT INTO clusters
               (id, statute_key, canonical_question, method, threshold)
               VALUES (?, ?, ?, 'sample-manifest', 1.0)""",
            (
                _id("CLUSTER", cluster["id"]),
                cluster["statute_key"],
                cluster["name"],
            ),
        )
        for member in cluster["members"]:
            connection.execute(
                "INSERT INTO cluster_members (cluster_id, proposition_id) VALUES (?, ?)",
                (_id("CLUSTER", cluster["id"]), proposition_ids[member]),
            )

    cluster_by_id = {cluster["id"]: cluster for cluster in manifest["clusters"]}
    inserted_pairs = 0
    for pair in manifest["hc_pairs"]:
        cluster_id = pair["cluster_id"]
        if cluster_id is None:
            cluster_id = f"UNCLUSTERED-{pair['pair_id']}"
            cluster = {
                "id": cluster_id,
                "statute_key": pair["statute_key"],
                "name": "Manifest pair outside a planted cluster",
                "sc_props": [],
                "sc_status": "NOT_APPLICABLE",
            }
            connection.execute(
                """INSERT INTO clusters
                   (id, statute_key, canonical_question, method, threshold)
                   VALUES (?, ?, ?, 'sample-manifest', 1.0)""",
                (_id("CLUSTER", cluster_id), cluster["statute_key"], cluster["name"]),
            )
        else:
            cluster = cluster_by_id[cluster_id]
        sc_props = cluster["sc_props"]
        sc_prop_id = proposition_ids[sc_props[0]] if sc_props else None
        connection.execute(
            """INSERT INTO pair_labels
               (id, statute_key, cluster_id, prop_a_id, prop_b_id, candidate_score,
                label, reason, votes_json, confidence, sc_status, sc_prop_id)
               VALUES (?, ?, ?, ?, ?, 1.0, ?, ?, ?, 1.0, ?, ?)""",
            (
                _id("PAIR", pair["pair_id"]),
                pair["statute_key"],
                _id("CLUSTER", cluster_id),
                proposition_ids[pair["prop_a"]],
                proposition_ids[pair["prop_b"]],
                pair["gold_label"],
                "SAMPLE DATA ONLY. " + pair["reason"],
                json.dumps([pair["gold_label"]] * 3),
                cluster["sc_status"],
                sc_prop_id,
            ),
        )
        connection.execute(
            """INSERT INTO gold_pairs
               (id, statute_key, prop_a_id, prop_b_id, annotator_1_label,
                annotator_2_label, final_gold_label, split)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'test')""",
            (
                _id("GOLD", pair["pair_id"]),
                pair["statute_key"],
                proposition_ids[pair["prop_a"]],
                proposition_ids[pair["prop_b"]],
                pair["gold_label"],
                pair["gold_label"],
                pair["gold_label"],
            ),
        )
        inserted_pairs += 1

    connection.commit()
    connection.close()
    return len(manifest["judgments"]), inserted_pairs, len(manifest["clusters"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    parser.add_argument("--raw-pdfs", type=Path, default=RAW_PDFS_DIR)
    args = parser.parse_args()
    judgments, pairs, clusters = load_sample_database(args.database, args.raw_pdfs)
    print(f"Replaced database with {judgments} sample judgments, {clusters} clusters, and {pairs} labeled pairs.")
    print(f"Copied PDFs to {args.raw_pdfs}")


if __name__ == "__main__":
    main()
