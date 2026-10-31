import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.adjudicator import _majority_vote
from backend.main import _source_uri
from backend.s3_ingest import download_public_s3_object
from backend.passage_selector import select_passages
from backend.pdf_processor import extract_pdf_pages
import backend.db as db
import backend.real_data as real_data
from mock_data.load_mock_database import load_demo_data
from sample_data.load_sample_database import load_sample_database


class ProjectFixTests(unittest.TestCase):
    def test_passage_selector_accepts_common_uploaded_statute_labels(self) -> None:
        pages = [
            "Subject: NI Act 138\nStatus: Accepted",
            "Statute: CrPC 482\nJurisdiction: Delhi HC",
            "Statute: Arbitration Act 11\nJurisdiction: Delhi HC",
        ]
        selected = select_passages(pages)
        self.assertEqual(
            {passage.statute_key for passage in selected},
            {"NI_ACT_S138", "CRPC_S482", "ARB_ACT_S11"},
        )

    def test_sample_loader_replaces_database_with_manifest_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = load_sample_database(root / "sample.db", root / "raw_pdfs")

            connection = sqlite3.connect(root / "sample.db")
            counts = {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("courts", "judgments", "propositions", "pair_labels")
            }
            verified = connection.execute(
                "SELECT COUNT(*) FROM propositions WHERE verify_status LIKE 'VERIFIED%'"
            ).fetchone()[0]
            connection.close()

            self.assertEqual(result, (28, 21, 7))
            self.assertEqual(counts, {
                "courts": 4,
                "judgments": 28,
                "propositions": 28,
                "pair_labels": 21,
            })
            self.assertEqual(verified, 28)
            self.assertEqual(len(list((root / "raw_pdfs").glob("*.pdf"))), 28)

    def test_demo_loader_is_idempotent_and_links_sc_only_as_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "demo.db"
            first = load_demo_data(database_path)
            second = load_demo_data(database_path)

            connection = sqlite3.connect(database_path)
            courts = connection.execute(
                "SELECT level, COUNT(*) FROM courts GROUP BY level ORDER BY level"
            ).fetchall()
            edges = connection.execute(
                """SELECT c_a.level, c_b.level, pl.sc_prop_id, pl.sc_status, pl.reason
                   FROM pair_labels pl
                   JOIN propositions pa ON pa.id=pl.prop_a_id
                   JOIN judgments ja ON ja.id=pa.judgment_id
                   JOIN courts c_a ON c_a.id=ja.court_id
                   JOIN propositions pb ON pb.id=pl.prop_b_id
                   JOIN judgments jb ON jb.id=pb.judgment_id
                   JOIN courts c_b ON c_b.id=jb.court_id"""
            ).fetchall()
            connection.close()

            self.assertEqual(first, (4, 2))
            self.assertEqual(second, (4, 0))
            self.assertEqual(courts, [("HC", 3), ("SC", 1)])
            self.assertEqual(len(edges), 2)
            self.assertTrue(all(row[0] == row[1] == "HC" for row in edges))
            self.assertTrue(all(row[2] and "Supreme Court fixture" in row[3] for row in edges))
            self.assertTrue(all("FAKE TEST DATA ONLY" in row[4] for row in edges))

    def test_groq_provider_without_key_is_deterministic(self) -> None:
        import backend.llm_client as llm_client

        with (
            patch.object(llm_client, "LLM_PROVIDER", "groq"),
            patch.object(llm_client, "GROQ_API_KEY", ""),
        ):
            self.assertEqual(llm_client.active_provider(), "rule-based")

    def test_real_corpus_import_preserves_existing_database_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_root = root / "corpus"
            (data_root / "processed").mkdir(parents=True)
            (data_root / "extracted_text").mkdir()
            source_text = "A source passage from the imported judgment."
            (data_root / "extracted_text" / "doc-1.txt").write_text(source_text, encoding="utf-8")
            record = {
                "chunk_index": 0,
                "document_id": "doc-1",
                "judgment_text": source_text,
                "case_number": "CASE-1",
                "decision_date": "2026-01-01",
                "disposal_nature": ["DISPOSED"],
                "court": "Patna High Court",
            }
            (data_root / "processed" / "benchsplit_dataset.jsonl").write_text(
                json.dumps(record) + "\n", encoding="utf-8"
            )
            database_path = root / "benchsplit.db"

            with (
                patch.object(db, "DATABASE_PATH", database_path),
                patch.object(real_data, "REAL_DATA_DIR", data_root),
            ):
                db.init_db()
                with db.db_connection() as connection:
                    connection.execute(
                        "INSERT INTO courts (id, name, short_code, level) VALUES ('EXISTING', 'Existing Court', 'EX', 'HC')"
                    )
                    connection.execute(
                        """INSERT INTO judgments
                           (id, court_id, cnr, title, decision_date, s3_uri, local_pdf_path,
                            pdf_sha256, has_text_layer, n_pages)
                           VALUES ('existing-judgment', 'EXISTING', 'EX-1', 'Existing',
                                   '2026-01-01', 'local://existing', 'existing.pdf', '', 1, 1)"""
                    )
                self.assertEqual(real_data.ensure_real_data_loaded(), 1)
                with db.db_connection() as connection:
                    existing = connection.execute(
                        "SELECT title FROM judgments WHERE id='existing-judgment'"
                    ).fetchone()
                    imported = connection.execute(
                        "SELECT COUNT(*) FROM judgments WHERE id='REAL-J-doc-1'"
                    ).fetchone()[0]

            self.assertEqual(existing["title"], "Existing")
            self.assertEqual(imported, 1)

    def test_groq_request_uses_configured_bearer_token(self) -> None:
        import backend.llm_client as llm_client

        response = Mock()
        response.json.return_value = {
            "choices": [{"message": {"content": '{"ok": true}'}}]
        }
        with (
            patch.object(llm_client, "GROQ_API_KEY", "test-token"),
            patch.object(llm_client.httpx, "post", return_value=response) as post,
        ):
            content = llm_client._request_groq("test prompt")

        self.assertEqual(content, '{"ok": true}')
        self.assertEqual(
            post.call_args.kwargs["headers"]["Authorization"],
            "Bearer test-token",
        )

    def test_majority_reason_comes_from_winning_label(self) -> None:
        label, reason, confidence = _majority_vote(
            [
                ("CONFLICT", "The first vote found a conflict."),
                ("AGREE", "The majority found agreement."),
                ("AGREE", "The second agreement vote."),
            ]
        )

        self.assertEqual(label, "AGREE")
        self.assertEqual(reason, "The majority found agreement.")
        self.assertAlmostEqual(confidence, 2 / 3)

    def test_public_s3_download_hashes_in_chunks(self) -> None:
        payload = b"judgment-content" * 100
        client = Mock()

        def download_file(_bucket: str, _key: str, destination: str) -> None:
            Path(destination).write_bytes(payload)

        client.download_file.side_effect = download_file
        with tempfile.TemporaryDirectory() as directory:
            with patch("boto3.client", return_value=client):
                path, digest = download_public_s3_object(
                    "public-bucket", "judgment.pdf", Path(directory) / "judgment.pdf"
                )

            self.assertEqual(path.read_bytes(), payload)
            self.assertEqual(digest, hashlib.sha256(payload).hexdigest())

    def test_local_documents_are_not_presented_as_s3_sources(self) -> None:
        self.assertEqual(
            _source_uri("J-DLHC-NI_ACT_S138", "DEMO123", "s3://fake", "raw/demo.pdf"),
            "demo://synthetic/demo.pdf",
        )
        self.assertEqual(
            _source_uri("random-id", "UPLOAD123", "s3://fake", "inbox/upload.pdf"),
            "local://inbox/upload.pdf",
        )
        self.assertEqual(
            _source_uri("external-id", "CNR123", "s3://real/source.pdf", "raw/source.pdf"),
            "s3://real/source.pdf",
        )

    def test_upload_without_court_is_not_attributed_to_delhi(self) -> None:
        import backend.main as main

        with tempfile.TemporaryDirectory() as directory:
            pdf_path = Path(directory) / "upload.pdf"
            pdf_path.write_bytes(b"%PDF-test")
            connection = sqlite3.connect(":memory:")
            connection.row_factory = sqlite3.Row
            connection.executescript(
                """
                CREATE TABLE courts (
                    id TEXT PRIMARY KEY, name TEXT, short_code TEXT, level TEXT
                );
                CREATE TABLE judgments (
                    id TEXT PRIMARY KEY, court_id TEXT, cnr TEXT, title TEXT,
                    decision_date TEXT, s3_uri TEXT, local_pdf_path TEXT,
                    pdf_sha256 TEXT, has_text_layer INTEGER, n_pages INTEGER
                );
                """
            )

            @contextmanager
            def database_connection():
                yield connection
                connection.commit()

            passage = SimpleNamespace(
                statute_key="NI_ACT_S138",
                page_num=1,
                text="A selected statutory passage.",
                page_char_offset=0,
                page_text="A selected statutory passage.",
            )
            run_events = []
            with (
                patch.object(main, "db_connection", database_connection),
                patch.object(main, "extract_pdf_pages", return_value=["A selected statutory passage."]),
                patch.object(main, "select_passages", return_value=[passage]),
                patch.object(main, "append_run_event", side_effect=lambda *args: run_events.append(args)),
                patch.object(main, "run_extraction", return_value={"final_status": "ACCEPTED"}),
                patch.object(main, "sha256_file", return_value="sha256"),
                patch.object(main, "finish_run") as finish_run,
            ):
                main._ingest_pdf(pdf_path, "upload.pdf", "run-id")

            judgment = connection.execute(
                "SELECT court_id, s3_uri FROM judgments"
            ).fetchone()
            court = connection.execute("SELECT name FROM courts WHERE id='UPLOAD'").fetchone()
            self.assertEqual(judgment["court_id"], "UPLOAD")
            self.assertEqual(judgment["s3_uri"], "local://inbox/upload.pdf")
            self.assertEqual(court["name"], "Uploaded judgment (court unverified)")
            self.assertTrue(any(event[2] == "skipped" for event in run_events))
            finish_run.assert_called_once()
            connection.close()


if __name__ == "__main__":
    unittest.main()
