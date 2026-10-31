# BenchSplit: Verified Legal Conflict Radar (Agentic IDE Master Specification)

> This `README.md` documents **BenchSplit**. Do NOT invent paid cloud services or vector databases (no Pinecone, Qdrant, or Chroma), do NOT use LangChain wrappers, and preserve the documented SQLite tables and JSON API contracts. Core storage and processing are local; hosted inference is optional.

---

## 1. System Overview & Core Architecture

**BenchSplit** detects horizontal legal conflicts (splits in interpretation on the exact same statutory provision) across 25 Indian High Courts and checks whether the Supreme Court of India has resolved the question within the scanned corpus.

### Core Engineering Guarantees
1. **Zero-Hallucination Evidence Lock**: No legal proposition is accepted into the database unless its `quote` field is deterministically verified against the raw PDF text layer (exact normalized substring match or fuzzy token ratio $\ge 92\%$) and mapped to exact page and character offsets (`page`, `char_start`, `char_end`).
2. **LangGraph Self-Correcting Extraction**: Per-judgment extraction runs as a stateful graph (`Extract -> Verify -> Repair [max 2 retries] -> Entailment -> Accept/Drop`). All state transitions stream live to the UI via Server-Sent Events (SSE).
3. **Algorithmic Blocking & Pair Ranking**: Avoids $\mathcal{O}(N^2)$ full pairwise LLM comparisons by blocking strictly on normalized `statute_key`, clustering questions via embeddings (`all-MiniLM-L6-v2`), filtering for cross-court pairs ($C_a \neq C_b$), and ranking candidates by:
   $$S(a, b) = \cos(\mathbf{q}_a, \mathbf{q}_b) - \cos(\mathbf{h}_a, \mathbf{h}_b)$$
4. **Scientific Evaluation Engine**: Computes Precision, Recall, $F_1$ score, Cohen's Kappa ($\kappa$) over the stored label columns, verifier drop rate, and compares conflict labels with a candidate-score threshold reference on a held-out test split. Seeded labels are synthetic demonstration data, not independent human annotations.
5. **Inference providers**: Uses `Groq` (`llama-3.1-8b-instant`) when `GROQ_API_KEY` is configured, with a deterministic rule-based fallback. Gemini and Ollama remain optional provider choices; Ollama is not required.

---

## 2. Exact Repository Directory Structure

The Agentic IDE must create and maintain this exact folder tree:

```text
benchsplit/
├── README.md
├── .env.example
├── requirements.txt
├── data/
│   ├── raw_pdfs/                  # Ingested source PDFs
│   ├── inbox/                     # Watched folder for live PDF drop demo
│   ├── page_cache/                # Rendered PNG pages with highlighted quotes
│   ├── briefs/                    # Generated 1-page PDF Forum-Risk Briefs
│   └── benchsplit.db              # SQLite database (auto-initialized)
├── backend/
│   ├── __init__.py
│   ├── config.py                  # Env vars, paths, LLM provider config
│   ├── db.py                      # SQLite connection, schema init, helper queries
│   ├── schema.sql                 # Complete DDL for all 8 tables
│   ├── models.py                  # Strict Pydantic v2 schemas for LLM & API
│   ├── llm_client.py              # Unified Ollama + Free Groq fallback client
│   ├── s3_ingest.py               # Anonymous boto3 S3 fetcher + SHA-256 provenance
│   ├── pdf_processor.py           # pdfplumber char-offset extractor + pypdfium2 highlighter
│   ├── passage_selector.py        # Regex statute blocker & paragraph window extractor
│   ├── verifier.py                # Deterministic normalized substring + rapidfuzz verifier
│   ├── langgraph_pipeline.py      # LangGraph state machine (Extract->Verify->Repair->Entail)
│   ├── clustering.py              # MiniLM embeddings, AgglomerativeClustering, pair scorer
│   ├── adjudicator.py             # 3-vote self-consistency conflict judge + SC resolution check
│   ├── evaluator.py               # Precision, Recall, F1, Cohen's Kappa, Baseline comparator
│   ├── brief_generator.py         # ReportLab 1-page PDF forum-risk brief generator
│   ├── real_data.py               # Imports the checked-out real corpus into SQLite
│   └── main.py                    # FastAPI app, REST endpoints, SSE stream, inbox watcher
└── frontend/                      # Structured Nyaaychakra React + Vite + Tailwind UI
    ├── package.json
    ├── vite.config.ts
    ├── index.html
    └── src/
        ├── data/screens.ts        # Workspace navigation/search metadata
        ├── main.tsx
        ├── App.tsx
        ├── types/api.ts           # Mirrors backend/models.py 1:1
        ├── pages/pages.tsx        # Landing page and routed workspace screens
        ├── services/api.ts        # Typed REST and SSE client used by the pages
        ├── assets/                # Frontend-owned artwork
        └── components/            # Navigation, evidence, graph, and pipeline UI
```

---

## 3. Complete Tech Stack & Dependencies

### Backend (`requirements.txt`)
Create `requirements.txt` with these exact packages:
```text
fastapi==0.115.0
uvicorn[standard]==0.30.6
pydantic==2.9.2
sse-starlette==2.1.3
python-multipart==0.0.12
langgraph==0.2.28
langchain-core==0.3.6
httpx==0.27.2
pdfplumber==0.11.4
pypdfium2==4.30.0
Pillow==10.4.0
rapidfuzz==3.10.0
sentence-transformers==3.1.1
scikit-learn==1.5.2
numpy==1.26.4
boto3==1.35.29
reportlab==4.2.5
watchdog==5.0.3
python-dotenv==1.0.1
```

### Frontend (`frontend/package.json` dependencies)
Ensure the frontend includes:
```json
{
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^7.18.5",
    "cytoscape": "^3.30.2",
    "lucide-react": "^0.446.0",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.5.2"
  },
  "devDependencies": {
    "@types/cytoscape": "^3.21.8",
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.47",
    "tailwindcss": "^3.4.13",
    "typescript": "^5.5.3",
    "vite": "^5.4.8"
  }
}
```

---

## 4. Database Schema (`backend/schema.sql`)

Write this exact SQL into `backend/schema.sql` and execute it via `conn.executescript()` on startup in `backend/db.py`:

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS courts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    short_code TEXT NOT NULL,
    level TEXT NOT NULL CHECK (level IN ('HC', 'SC'))
);

CREATE TABLE IF NOT EXISTS judgments (
    id TEXT PRIMARY KEY,
    court_id TEXT NOT NULL REFERENCES courts(id),
    cnr TEXT NOT NULL,
    title TEXT NOT NULL,
    decision_date TEXT NOT NULL,
    s3_uri TEXT NOT NULL,
    local_pdf_path TEXT NOT NULL,
    pdf_sha256 TEXT NOT NULL,
    has_text_layer INTEGER NOT NULL DEFAULT 1,
    n_pages INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS propositions (
    id TEXT PRIMARY KEY,
    judgment_id TEXT NOT NULL REFERENCES judgments(id),
    statute_key TEXT NOT NULL,
    question TEXT NOT NULL,
    holding TEXT NOT NULL,
    quote TEXT NOT NULL,
    page INTEGER NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    verify_status TEXT NOT NULL CHECK (verify_status IN ('VERIFIED_EXACT', 'VERIFIED_FUZZY', 'DROPPED')),
    verify_score REAL NOT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    entailment_supported INTEGER NOT NULL DEFAULT 1,
    model_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL DEFAULT 'v1.0',
    embedding_q BLOB,
    embedding_h BLOB
);

CREATE TABLE IF NOT EXISTS clusters (
    id TEXT PRIMARY KEY,
    statute_key TEXT NOT NULL,
    canonical_question TEXT NOT NULL,
    method TEXT NOT NULL DEFAULT 'agglomerative_cosine',
    threshold REAL NOT NULL DEFAULT 0.35
);

CREATE TABLE IF NOT EXISTS cluster_members (
    cluster_id TEXT NOT NULL REFERENCES clusters(id),
    proposition_id TEXT NOT NULL REFERENCES propositions(id),
    PRIMARY KEY (cluster_id, proposition_id)
);

CREATE TABLE IF NOT EXISTS pair_labels (
    id TEXT PRIMARY KEY,
    statute_key TEXT NOT NULL,
    cluster_id TEXT NOT NULL REFERENCES clusters(id),
    prop_a_id TEXT NOT NULL REFERENCES propositions(id),
    prop_b_id TEXT NOT NULL REFERENCES propositions(id),
    candidate_score REAL NOT NULL,
    label TEXT NOT NULL CHECK (label IN ('CONFLICT', 'AGREE', 'DISTINGUISHABLE_ON_FACTS', 'UNRELATED')),
    reason TEXT NOT NULL,
    votes_json TEXT NOT NULL,
    confidence REAL NOT NULL,
    sc_status TEXT NOT NULL,
    sc_prop_id TEXT REFERENCES propositions(id)
);

CREATE TABLE IF NOT EXISTS gold_pairs (
    id TEXT PRIMARY KEY,
    statute_key TEXT NOT NULL,
    prop_a_id TEXT NOT NULL REFERENCES propositions(id),
    prop_b_id TEXT NOT NULL REFERENCES propositions(id),
    annotator_1_label TEXT NOT NULL,
    annotator_2_label TEXT NOT NULL,
    final_gold_label TEXT NOT NULL,
    split TEXT NOT NULL CHECK (split IN ('tune', 'test'))
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    filename TEXT,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    events_json TEXT NOT NULL DEFAULT '[]',
    metrics_json TEXT NOT NULL DEFAULT '{}'
);
```

---

## 5. Exact Pydantic Schemas & API Contracts (`backend/models.py`)

Both backend endpoints and frontend TypeScript interfaces (`frontend/src/types/api.ts`) **must** adhere strictly to these models:

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Literal

# --- LLM Structured Output Schemas ---
class LLMExtractionOutput(BaseModel):
    statute_key: str = Field(description="Normalized key, e.g., 'NI_ACT_S138' or 'ARB_ACT_S11'")
    question: str = Field(description="Single legal question answered by the court in one sentence")
    holding: str = Field(description="The court's affirmative/negative legal ruling on that question")
    quote: str = Field(description="EXACT verbatim substring copied character-for-character from the passage")

class LLMEntailmentOutput(BaseModel):
    supports: bool = Field(description="True ONLY if the verbatim quote directly supports the stated holding")
    rationale: str

class LLMAdjudicationOutput(BaseModel):
    label: Literal["CONFLICT", "AGREE", "DISTINGUISHABLE_ON_FACTS", "UNRELATED"]
    reason: str = Field(description="One-sentence legal explanation comparing Holding A and Holding B")

# --- REST API Response Schemas ---
class StatuteSummary(BaseModel):
    statute_key: str
    display_name: str
    total_judgments: int
    verified_propositions: int
    dropped_hallucinations: int
    conflict_count: int
    sc_status_badge: str

class GraphNode(BaseModel):
    id: str                  # proposition_id
    court_id: str
    court_name: str
    court_short: str
    level: Literal["HC", "SC"]
    judgment_title: str
    cnr: str
    decision_date: str
    holding_preview: str
    s3_uri: str

class GraphEdge(BaseModel):
    id: str                  # pair_label_id
    source: str              # prop_a_id
    target: str              # prop_b_id
    label: Literal["CONFLICT", "AGREE", "DISTINGUISHABLE_ON_FACTS"]
    confidence: float
    reason: str
    sc_status: str

class StatuteGraphResponse(BaseModel):
    statute_key: str
    display_name: str
    sc_scanned_count: int
    nodes: List[GraphNode]
    edges: List[GraphEdge]

class PropositionEvidence(BaseModel):
    proposition_id: str
    court_name: str
    judgment_title: str
    cnr: str
    decision_date: str
    s3_uri: str
    pdf_sha256: str
    question: str
    holding: str
    quote: str
    page: int
    char_start: int
    char_end: int
    verify_status: str
    verify_score: float
    retry_count: int
    page_image_url: str

class ConflictDetailResponse(BaseModel):
    conflict_id: str
    statute_key: str
    label: str
    reason: str
    votes: List[str]
    confidence: float
    candidate_score: float
    sc_status: str
    prop_a: PropositionEvidence
    prop_b: PropositionEvidence
    sc_prop: Optional[PropositionEvidence] = None

class EvalMetricsResponse(BaseModel):
    total_gold_pairs_test: int
    precision: float
    recall: float
    f1_score: float
    cohens_kappa: float
    baseline_f1_score: float
    f1_improvement_over_baseline: float
    total_extractions_attempted: int
    total_extractions_dropped: int
    hallucination_drop_rate: float
    confusion_matrix: dict  # {"TP": int, "FP": int, "TN": int, "FN": int}
    conflict_definition: str
```

---

## 6. Core Backend Algorithms (Anti-Hallucination Implementation Rules)

### 6.1 Statute Normalization & Regex Passage Selection (`backend/passage_selector.py`)
Never send a full 40-page judgment to the LLM.
1. Extract text per page with character offsets using `pdfplumber`.
2. Scan paragraphs using compiled regex patterns for our 3 target sections:
   - `NI_ACT_S138`: `r"(?i)section\s+138.*?(?:negotiable\s+instruments|n\.?i\.?\s+act)"`
   - `ARB_ACT_S11`: `r"(?i)section\s+11(?:\(6\))?.*?(?:arbitration|1996\s+act)"`
   - `CRPC_S482`: `r"(?i)section\s+482.*?(?:cr\.?p\.?c|code\s+of\s+criminal\s+procedure)"`
3. Keep only a $\pm 1$ paragraph window around matches (capped at 1,800 characters per passage).

### 6.2 Deterministic Quote Verifier (`backend/verifier.py`)
Given `passage_text`, `page_char_offset`, and `llm_quote`:
1. **Normalize Function**: Convert smart quotes (`“`, `”`, `‘`, `’`) to standard ASCII quotes, collapse multiple whitespace/newlines into a single space, and strip leading/trailing punctuation while maintaining an index map `norm_idx -> orig_idx`.
2. **Exact Substring Check**: If `norm(llm_quote)` is in `norm(passage_text)`, compute the exact `char_start` and `char_end` in the original page text. Return `status="VERIFIED_EXACT"`, `score=100.0`, and overwrite `llm_quote` with `orig_page_text[char_start:char_end]`.
3. **Fuzzy Substring Fallback**: Use `rapidfuzz.fuzz.partial_ratio_alignment(norm_quote, norm_passage)`. If `score >= 92.0`, map the alignment window back to `orig_page_text[char_start:char_end]` and return `status="VERIFIED_FUZZY"`.
4. **Reject**: If `score < 92.0`, return `status="FAILED"`, `error_msg="Quote not found verbatim in source passage. Copy an exact contiguous sentence from the text."`

### 6.3 LangGraph Per-Judgment State Machine (`backend/langgraph_pipeline.py`)
Define `ExtractionState(TypedDict)`:
```python
class ExtractionState(TypedDict):
    run_id: str
    judgment_id: str
    passage_text: str
    page_num: int
    statute_key: str
    raw_extraction: dict | None
    verify_status: str
    verify_score: float
    char_start: int
    char_end: int
    retry_count: int
    error_feedback: str | None
    entailment_passed: bool
    final_status: str  # "ACCEPTED" | "DROPPED"
```
**Graph Edges**:
- `START -> extract_node -> verify_node`
- Conditional edge from `verify_node`:
  - If `verify_status in ("VERIFIED_EXACT", "VERIFIED_FUZZY")` $\rightarrow$ `entailment_node`
  - If `verify_status == "FAILED"` and `retry_count < 2` $\rightarrow$ `repair_node` (increments `retry_count`, injects `error_feedback` into prompt) $\rightarrow$ `extract_node`
  - If `verify_status == "FAILED"` and `retry_count >= 2` $\rightarrow$ `drop_node` (`final_status = "DROPPED"`)
- Conditional edge from `entailment_node`:
  - If `entailment_passed == True` $\rightarrow$ `accept_node` (`final_status = "ACCEPTED"`)
  - Else $\rightarrow$ `drop_node`
- Every node appends a timestamped event `{ "node": name, "status": ..., "detail": ..., "retry": retry_count }` to the `runs` table so `GET /api/runs/{id}/events` streams live updates to the frontend.

### 6.4 Blocking, Clustering & Cross-Court Pair Scoring (`backend/clustering.py`)
1. Encode `question` and `holding` for all verified propositions in a `statute_key` block using `SentenceTransformer("all-MiniLM-L6-v2")` (or deterministic TF-IDF + SVD fallback if offline model weights aren't cached yet).
2. Run `AgglomerativeClustering(n_clusters=None, distance_threshold=0.35, metric="cosine", linkage="average")` on question embeddings $\mathbf{Q}$.
3. Inside each cluster, generate pairs $(a, b)$ where `court_id(a) != court_id(b)` and both are High Courts (`level == 'HC'`).
4. Compute candidate score:
   $$S(a, b) = \cos(\mathbf{q}_a, \mathbf{q}_b) - \cos(\mathbf{h}_a, \mathbf{h}_b)$$
5. Retain top $K=3$ highest-scoring pairs per cluster for LLM adjudication.

### 6.5 Self-Consistency Voting & Supreme Court Badge (`backend/adjudicator.py`)
1. Run the adjudication prompt on top candidate pairs.
2. If initial label is `CONFLICT`, execute 2 additional independent passes at `temperature=0.4` (total 3 votes). Majority label wins; `confidence = matching_votes / 3.0`.
3. **Supreme Court Check**: Query `propositions` where `statute_key` matches and `court.level == 'SC'`. If no SC proposition exists in the same question cluster, set `sc_status = f"No SC resolution found in {sc_count} SC judgments scanned"`. Never claim `"UNRESOLVED BY SC"` unconditionally.

### 6.6 PDF Page Rendering & Quote Highlighting (`backend/pdf_processor.py`)
When `GET /api/evidence/{proposition_id}/page.png` is requested:
1. Open `local_pdf_path` with `pypdfium2.PdfDocument` and `pdfplumber`.
2. Render page `page - 1` at `scale=2.0` to a `PIL.Image` (`RGBA`).
3. Using `pdfplumber` word bounding boxes intersecting `[char_start, char_end]`, draw a semi-transparent highlight rectangle (`fill=(250, 204, 21, 95)`, `outline=(220, 38, 38, 220)`, `width=2`) over the exact quote lines.
4. Synthetic seed PDFs include a visible footer and appendix stating that they are test fixtures, not authentic judgments or legal authority.

---

## 7. FastAPI Endpoints (`backend/main.py`)

Configure `CORSMiddleware(allow_origins=["*"])` and prefix all routes with `/api`:

Interactive REST documentation is available while the backend is running:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

When using the Vite frontend, the same paths are proxied at `http://127.0.0.1:5173/docs`, `/redoc`, and `/openapi.json`.

| Method | Route | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Returns API, model-provider, and corpus classification |
| `GET` | `/api/courts` | Returns known High Courts available for attributed uploads |
| `GET` | `/api/statutes` | Returns `List[StatuteSummary]` |
| `GET` | `/api/statutes/{statute_key}/graph` | Returns `StatuteGraphResponse` (nodes & edges for Cytoscape) |
| `GET` | `/api/conflicts/{conflict_id}` | Returns `ConflictDetailResponse` (full quotes, votes, S3 URIs, SHA-256) |
| `GET` | `/api/evidence/{proposition_id}` | Returns a single proposition and its source metadata |
| `GET` | `/api/evidence/{proposition_id}/page.png` | Returns `FileResponse` (`image/png`) with highlighted quote |
| `POST` | `/api/ingest` | Accepts `UploadFile` (`.pdf`), saves to `data/inbox/`, triggers LangGraph run, returns `{"run_id": ...}` |
| `POST` | `/api/demo/trigger-live-sim` | Triggers a deterministic live LangGraph run showing 1 repair cycle (Quote Failed $\rightarrow$ Repaired $\rightarrow$ Verified $\rightarrow$ New Edge Created) for stage reliability |
| `GET` | `/api/runs` | Returns persistent runs from the database, newest first |
| `GET` | `/api/runs/{run_id}` | Returns one persistent run, including events and metrics |
| `GET` | `/api/runs/{run_id}/events` | `EventSourceResponse` streaming JSON node state transitions every 400ms |
| `GET` | `/api/eval/summary` | Returns `EvalMetricsResponse` (Precision, Recall, $F_1$, $\kappa$, Confusion Matrix, Drop Rate) |
| `GET` | `/api/briefs/{statute_key}.pdf` | Generates and returns a 1-page `application/pdf` Forum-Risk Brief |

---

## 8. Real Corpus Import

If present, `backend/real_data.py` imports the `database_real_github/data` corpus into
the `REAL_CORPUS` statute on startup. That corpus is not included in this repository.
Without it, the API still starts against the local SQLite database and reports a
warning; the workspace is empty until data is imported or judgments are ingested.
The importer uses the real processed JSONL,
metadata, extracted text, and Supreme Court source text. It preserves exact source
URIs and hashes, and is idempotent after the first import.

Run the conservative one-time preprocessing command from the repository root:

```powershell
.\.venv\Scripts\python.exe -m backend.preprocess_real
.\.venv\Scripts\python.exe -m backend.preprocess_real --apply --copy-pdfs
```

The first command reports detected references without changing analysis results. The
second verifies imported quotes, creates embeddings/clusters, adjudicates only eligible
cross-court candidates, and copies source PDFs into `data/raw_pdfs`. The command refuses
to invent relationships; if the imported corpus has only one High Court jurisdiction,
it correctly reports zero cross-High-Court conflicts until another High Court corpus is
added.

The imported corpus contains source records, not precomputed legal conflict labels.
The API therefore does not invent conflict edges or semantic holdings. High Court
disposition metadata is shown as recorded source metadata; Supreme Court records are
available for review with semantic proposition extraction explicitly marked as pending.

Every relationship includes a concise explanation comparing both holdings. The
Conflict Radar shows the two holdings and their verified source quotations when a
relationship is selected. Set `LLM_PROVIDER=groq` and provide `GROQ_API_KEY` in
`.env` to use Groq for extraction, entailment checks, and relationship explanations;
otherwise the backend uses deterministic rules. Groq receives the extracted judgment
passage and related prompts, so only configure it if sending those excerpts to the
hosted provider is acceptable.

---

## 9. How to Run Locally

```bash
# 1. Backend Setup (PowerShell)
uv venv --python 3.11
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env and set GROQ_API_KEY to your Groq API key. Do not commit .env.

# 2. Start FastAPI Server (Port 8000); a checked-out real corpus is optional.
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 3. Frontend Setup (Port 5173)
cd frontend
npm ci
npm run dev
```

The Groq API key is **not included** in the repository. Add it locally to the root
`.env` file as `GROQ_API_KEY=your_key`; `.env.example` documents the variable and is
safe to commit because its key value is blank. The default model is
`openai/gpt-oss-20b`; change `GROQ_MODEL` only to a model available from your Groq
account. With no key, inference uses deterministic rules and does not call Ollama.

Run backend regression tests from the repository root with
`python -m unittest discover -s tests -v`.

To populate the empty local database with clearly marked demo records from three
fictional High Courts and one fictional Supreme Court judgment, run:

```powershell
python -m mock_data.generate_mock_dataset
python -m mock_data.load_mock_database
```

The loader adds two fictional High-Court conflict edges and links the fictional
Supreme Court proposition as a resolution fixture. It is additive and safe to
rerun; all records are visibly marked as fake test data, not legal authority.

To replace the local demo corpus with the supplied 28-document synthetic corpus,
including its PDFs, planted clusters, pair labels, and Supreme Court references,
run:

```powershell
Copy-Item data\benchsplit.db data\benchsplit.db.before_sample.bak
python -m sample_data.load_sample_database
```

This replacement copies the PDFs into `data\raw_pdfs` and rebuilds the active
SQLite demo tables from `sample_data\benchsplit_synthetic_corpus\manifest.json`.
The corpus is fictional and must not be used as legal authority.

The ingestion page accepts one or more PDF files in a single selection or drag-and-drop
operation. Each file receives an independent processing run, and the processing screen
shows the live events for every uploaded file.

The frontend reads statutes, graphs, conflicts, source evidence, evaluation
metrics, run history, health, and generated briefs from the backend API. PDF
ingestion is uploaded to the backend and its run events are streamed live.
There are no frontend mock-data fixtures. The imported corpus is a research
dataset and every source still requires qualified legal review before reliance.

---

## 10. Attribution & Legal Disclaimer
- **External source attribution**: Retain the source dataset's license and attribution when redistributing records from `database_real_github`.
- **Disclaimer**: BenchSplit is an academic research prototype for legal conflict discovery and does not constitute legal advice. All outputs require verification by qualified legal counsel.