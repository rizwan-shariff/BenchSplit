# FAKE TEST DATA ONLY

This folder is a completely fabricated test corpus. It is not sourced from any
court, is not legal authority, and must never be presented as real case law. The
Supreme Court case and the High Court cases are also fictional.

It contains mock judgments for:

- Bombay High Court
- Delhi High Court
- Karnataka High Court (Bengaluru)
- Supreme Court of India

The records intentionally contain opposing holdings for the same fictional
Section 138 question so the Conflict Radar can be tested. Every record uses a
`fake://FAKE_TEST_DATA/` source URI.

Generate or regenerate the fixture files with:

```powershell
.\.venv\Scripts\python.exe mock_data\generate_mock_dataset.py
```

Generated files:

- `data/processed/benchsplit_dataset.jsonl`
- `data/processed/benchsplit_dataset.csv`
- `data/metadata/*.json`
- `data/extracted_text/*.txt`
- `expected_conflicts.json`

The mock corpus is intentionally separate from `database_real_github` and is
not loaded by backend startup.

To add the fake fixtures to the backend's configured SQLite database (default
`data/benchsplit.db`):

```powershell
python -m mock_data.generate_mock_dataset
python -m mock_data.load_mock_database
```

Loading is additive and idempotent; it does not delete or replace other database
records. The seeded conflicts connect only fictional High Courts. The fictional
Supreme Court proposition is attached as an appellate-resolution fixture, not
as a conflict edge. All fixture relationships are synthetic UI/demo labels, not
legal conclusions. The fixture sources are text files, not PDFs, so PDF page
images are unavailable for them.
