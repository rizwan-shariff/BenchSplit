import asyncio
import json
import logging
import re
import threading
import time
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse
from watchdog.events import FileSystemEventHandler

from backend.config import (
    INBOX_DIR,
    LLM_PROVIDER,
    STATUTE_NAMES,
)
from backend.db import (
    append_run_event,
    create_run,
    db_connection,
    finish_run,
    get_run,
    get_run_events,
    init_db,
    resolve_path,
)
from backend.evaluator import calculate_metrics
from backend.langgraph_pipeline import run_extraction
from backend.models import (
    ConflictDetailResponse,
    CourtSummary,
    EvalMetricsResponse,
    GraphEdge,
    GraphNode,
    PropositionEvidence,
    StatuteGraphResponse,
    StatuteSummary,
)
from backend.pdf_processor import extract_pdf_pages, render_highlighted_page, sha256_file
from backend.passage_selector import select_passages

LOGGER = logging.getLogger(__name__)
app = FastAPI(title="BenchSplit API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _validate_statute(statute_key: str) -> None:
    if statute_key not in STATUTE_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown statute key: {statute_key}")


def _source_uri(judgment_id: str, cnr: str, stored_uri: str, local_pdf_path: str) -> str:
    filename = Path(local_pdf_path).name
    if stored_uri.startswith("real://"):
        return stored_uri
    if judgment_id.startswith("J-"):
        return f"demo://synthetic/{filename}"
    if cnr.startswith("UPLOAD"):
        return f"local://inbox/{filename}"
    return stored_uri


def _evidence(connection, proposition_id: str) -> Optional[dict[str, Any]]:
    row = connection.execute(
        """SELECT p.*, j.title AS judgment_title, j.cnr, j.decision_date, j.s3_uri,
                  j.pdf_sha256, j.local_pdf_path, c.name AS court_name
           FROM propositions p JOIN judgments j ON j.id=p.judgment_id
           JOIN courts c ON c.id=j.court_id WHERE p.id=?""",
        (proposition_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "proposition_id": row["id"],
        "court_name": row["court_name"],
        "judgment_title": row["judgment_title"],
        "cnr": row["cnr"],
        "decision_date": row["decision_date"],
        "s3_uri": _source_uri(
            row["judgment_id"], row["cnr"], row["s3_uri"], row["local_pdf_path"]
        ),
        "pdf_sha256": row["pdf_sha256"],
        "question": row["question"],
        "holding": row["holding"],
        "quote": row["quote"],
        "page": row["page"],
        "char_start": row["char_start"],
        "char_end": row["char_end"],
        "verify_status": row["verify_status"],
        "verify_score": row["verify_score"],
        "retry_count": row["retry_count"],
        "page_image_url": f"/api/evidence/{proposition_id}/page.png",
    }


def _graph_node(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "court_id": row["court_id"],
        "court_name": row["court_name"],
        "court_short": row["court_short"],
        "level": row["level"],
        "judgment_title": row["judgment_title"],
        "cnr": row["cnr"],
        "decision_date": row["decision_date"],
        "holding_preview": row["holding_preview"],
        "s3_uri": _source_uri(
            row["judgment_id"], row["cnr"], row["s3_uri"], row["local_pdf_path"]
        ),
    }


def _background_error(run_id: str, error: Exception) -> None:
    LOGGER.exception("Background ingestion failed", exc_info=error)
    try:
        append_run_event(run_id, "Ingestion", "failed", str(error))
        current = get_run(run_id)
        if current and not current["ended_at"]:
            finish_run(run_id, "failed")
    except LookupError:
        LOGGER.error("Cannot record failure for missing run %s", run_id)


def _ingest_pdf(
    pdf_path: Path, filename: str, run_id: str, court_id: str = "UPLOAD"
) -> None:
    try:
        pages = extract_pdf_pages(pdf_path)
        passages = select_passages(pages)
        if not passages:
            append_run_event(run_id, "Passage Selection", "dropped", "No supported statute section matched the PDF text.")
            finish_run(run_id, "completed")
            return
        passage = passages[0]
        append_run_event(
            run_id, "Passage Selection", "selected",
            f"Selected {passage.statute_key} passage from page {passage.page_num}.",
        )
        judgment_id = str(uuid.uuid4())
        with db_connection() as connection:
            if court_id == "UPLOAD":
                connection.execute(
                    """INSERT OR IGNORE INTO courts (id, name, short_code, level)
                       VALUES ('UPLOAD', 'Uploaded judgment (court unverified)', 'UPLOAD', 'HC')"""
                )
            else:
                court = connection.execute(
                    "SELECT id, level FROM courts WHERE id=?", (court_id,)
                ).fetchone()
                if court is None or court["level"] != "HC":
                    raise ValueError(f"Unknown or non-High-Court upload court: {court_id}")
            connection.execute(
                """INSERT INTO judgments
                   (id, court_id, cnr, title, decision_date, s3_uri, local_pdf_path,
                    pdf_sha256, has_text_layer, n_pages)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                (
                    judgment_id, court_id, f"UPLOAD{uuid.uuid4().hex[:16].upper()}",
                    Path(filename).stem, date.today().isoformat(),
                    f"local://inbox/{pdf_path.name}",
                    str(pdf_path), sha256_file(pdf_path), len(pages),
                ),
            )
        result = run_extraction(
            run_id, judgment_id, passage.text, passage.page_num, passage.statute_key,
            passage.page_char_offset, passage.page_text, complete_run=False,
        )
        if result["final_status"] == "ACCEPTED" and court_id != "UPLOAD":
            from backend.clustering import cluster_statute_and_adjudicate

            append_run_event(run_id, "Clustering", "running", "Embedding and blocking verified propositions.")
            adjudicated = cluster_statute_and_adjudicate(passage.statute_key)
            append_run_event(
                run_id, "Clustering", "completed",
                f"Ranked and adjudicated {adjudicated} cross-court candidate pair(s).",
            )
        elif result["final_status"] == "ACCEPTED":
            append_run_event(
                run_id, "Clustering", "skipped",
                "Court was not provided; the proposition is excluded from cross-court comparison.",
            )
        finish_run(run_id, "completed", {"final_status": result["final_status"]})
    except Exception as error:
        _background_error(run_id, error)


def _run_live_simulation(run_id: str) -> None:
    try:
        with db_connection() as connection:
            row = connection.execute(
                """SELECT p.id, p.judgment_id, p.statute_key, p.question, p.holding, p.quote,
                          p.page, p.char_start, p.char_end, j.court_id
                   FROM propositions p JOIN judgments j ON j.id=p.judgment_id
                   WHERE p.id LIKE 'P-%'
                     AND p.verify_status IN ('VERIFIED_EXACT','VERIFIED_FUZZY')
                   ORDER BY CASE p.statute_key WHEN 'NI_ACT_S138' THEN 0 ELSE 1 END, p.id
                   LIMIT 1"""
            ).fetchone()
        if row is None:
            raise RuntimeError("No verified seed proposition exists for the live simulation")
        seed = dict(row)
        pdf_path = resolve_path(
            db_connection_path(seed["judgment_id"])
        )
        pages = extract_pdf_pages(pdf_path)
        page_text = pages[seed["page"] - 1]
        append_run_event(
            run_id, "Passage Selection", "selected",
            f"Selected {seed['statute_key']} passage from page {seed['page']}.",
        )
        attempt = {"count": 0}

        def simulated_extractor(state: dict) -> dict:
            attempt["count"] += 1
            quote = (
                "This invented quotation is absent from the source document."
                if attempt["count"] == 1 else seed["quote"]
            )
            return {
                "statute_key": seed["statute_key"],
                "question": seed["question"],
                "holding": seed["holding"],
                "quote": quote,
            }

        result = run_extraction(
            run_id, seed["judgment_id"], seed["quote"], seed["page"],
            seed["statute_key"], seed["char_start"], page_text,
            extractor=simulated_extractor,
            entailment_checker=lambda quote, holding: (
                True, "Deterministic simulated quote supports the extracted holding."
            ),
            complete_run=False,
        )
        if result["final_status"] != "ACCEPTED":
            raise RuntimeError("Live repair simulation failed to verify its corrected quote")
        with db_connection() as connection:
            cluster = connection.execute(
                """SELECT id FROM clusters
                   WHERE statute_key=? AND canonical_question=? LIMIT 1""",
                (seed["statute_key"], seed["question"]),
            ).fetchone()
            if cluster is None:
                raise RuntimeError("No matching question cluster exists for the live simulation")
            cluster_id = cluster["id"]
            counterpart = connection.execute(
                """SELECT p.id FROM propositions p JOIN judgments j ON j.id=p.judgment_id
                   JOIN cluster_members cm ON cm.proposition_id=p.id
                   WHERE p.statute_key=? AND p.verify_status IN ('VERIFIED_EXACT','VERIFIED_FUZZY')
                     AND cm.cluster_id=? AND j.court_id<>? AND p.id<>? LIMIT 1""",
                (
                    seed["statute_key"], cluster_id, seed["court_id"],
                    result["proposition_id"],
                ),
            ).fetchone()
            if counterpart is None:
                raise RuntimeError("No cross-court proposition is available for the simulated edge")
            connection.execute(
                "INSERT INTO cluster_members (cluster_id, proposition_id) VALUES (?, ?)",
                (cluster_id, result["proposition_id"]),
            )
            sc_count = connection.execute(
                "SELECT COUNT(DISTINCT j.id) FROM judgments j JOIN courts c ON c.id=j.court_id WHERE c.level='SC'"
            ).fetchone()[0]
            sc_prop = connection.execute(
                """SELECT p.id FROM propositions p JOIN judgments j ON j.id=p.judgment_id
                   JOIN courts c ON c.id=j.court_id
                   JOIN cluster_members cm ON cm.proposition_id=p.id
                   WHERE p.statute_key=? AND c.level='SC' AND cm.cluster_id=? LIMIT 1""",
                (seed["statute_key"], cluster_id),
            ).fetchone()
            sc_status = (
                "SC proposition found in the statute corpus"
                if sc_prop else f"No SC resolution found in {sc_count} SC judgments scanned"
            )
            connection.execute(
                """INSERT INTO pair_labels
                   (id, statute_key, cluster_id, prop_a_id, prop_b_id, candidate_score, label,
                    reason, votes_json, confidence, sc_status, sc_prop_id)
                   VALUES (?, ?, ?, ?, ?, 0.0, 'CONFLICT', ?, ?, 1.0, ?, ?)""",
                (
                    str(uuid.uuid4()), seed["statute_key"], cluster_id,
                    result["proposition_id"], counterpart["id"],
                    "Simulated live-ingestion conflict edge added after verified repair.",
                    json.dumps(["CONFLICT", "CONFLICT", "CONFLICT"]), sc_status,
                    sc_prop["id"] if sc_prop else None,
                ),
            )
        append_run_event(run_id, "Conflict Edge Added", "added", "Verified simulated proposition linked across courts.")
        finish_run(run_id, "completed", {"final_status": "ACCEPTED"})
    except Exception as error:
        _background_error(run_id, error)


def db_connection_path(judgment_id: str) -> str:
    with db_connection() as connection:
        row = connection.execute(
            "SELECT local_pdf_path FROM judgments WHERE id=?", (judgment_id,)
        ).fetchone()
    if row is None:
        raise LookupError(f"Judgment {judgment_id} does not exist")
    return row["local_pdf_path"]


class _InboxHandler(FileSystemEventHandler):
    def __init__(self) -> None:
        self._seen: set[str] = set()
        self._lock = threading.Lock()

    def on_created(self, event) -> None:
        if event.is_directory or Path(event.src_path).suffix.lower() != ".pdf":
            return
        path = Path(event.src_path)
        if re.match(r"^[0-9a-f]{32}-", path.name):
            return
        with self._lock:
            if str(path) in self._seen:
                return
            self._seen.add(str(path))
        time.sleep(0.5)
        run_id = str(uuid.uuid4())
        try:
            create_run(run_id, "inbox", path.name)
            _ingest_pdf(path, path.name, run_id)
        except Exception as error:
            _background_error(run_id, error)


@app.on_event("startup")
def startup() -> None:
    init_db()
    from backend.config import MOCK_DATA_MODE

    if MOCK_DATA_MODE:
        return
    from backend.real_data import ensure_real_data_loaded

    try:
        ensure_real_data_loaded()
    except FileNotFoundError as error:
        LOGGER.warning(
            "Real corpus not found; starting with the existing local database. %s",
            error,
        )
    try:
        from watchdog.observers import Observer

        observer = Observer()
        observer.schedule(_InboxHandler(), str(INBOX_DIR), recursive=False)
        observer.start()
        app.state.inbox_observer = observer
    except ImportError:
        LOGGER.warning("watchdog is unavailable; inbox file watching is disabled")


@app.on_event("shutdown")
def shutdown() -> None:
    observer = getattr(app.state, "inbox_observer", None)
    if observer:
        observer.stop()
        observer.join(timeout=5)


@app.get("/api/health")
def health() -> dict[str, str]:
    provider = LLM_PROVIDER
    if provider == "groq":
        from backend.config import GROQ_API_KEY

        if not GROQ_API_KEY:
            provider = "rule-based"
    elif provider == "gemini":
        from backend.config import GEMINI_API_KEY

        if not GEMINI_API_KEY:
            provider = "rule-based"
    with db_connection() as connection:
        dataset = connection.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN s3_uri LIKE 'demo://synthetic/%'
                                OR s3_uri LIKE 'fake://FAKE_TEST_DATA/%'
                               THEN 1 ELSE 0 END) AS synthetic
               FROM judgments"""
        ).fetchone()
    total = int(dataset["total"] or 0)
    synthetic = int(dataset["synthetic"] or 0)
    dataset_mode = (
        "empty"
        if total == 0
        else "synthetic-test"
        if synthetic == total
        else "mixed"
        if synthetic > 0
        else "ingested"
    )
    return {
        "status": "ok",
        "llm_provider": provider,
        "dataset_mode": dataset_mode,
    }


@app.get("/api/courts", response_model=list[CourtSummary])
def courts() -> list[dict[str, str]]:
    with db_connection() as connection:
        rows = connection.execute(
            "SELECT id, name, short_code FROM courts WHERE level='HC' AND id<>'UPLOAD' ORDER BY name"
        ).fetchall()
    return [dict(row) for row in rows]


@app.get("/api/statutes", response_model=list[StatuteSummary])
def statutes() -> list[dict[str, Any]]:
    summaries = []
    with db_connection() as connection:
        for statute_key, display_name in STATUTE_NAMES.items():
            row = connection.execute(
                """SELECT COUNT(DISTINCT CASE WHEN p.verify_status!='DROPPED' THEN j.id END) AS judgments,
                          SUM(CASE WHEN p.verify_status IN ('VERIFIED_EXACT','VERIFIED_FUZZY') THEN 1 ELSE 0 END) AS verified,
                          SUM(CASE WHEN p.verify_status='DROPPED' THEN 1 ELSE 0 END) AS dropped
                   FROM propositions p JOIN judgments j ON j.id=p.judgment_id
                   WHERE p.statute_key=?""",
                (statute_key,),
            ).fetchone()
            if not row["judgments"] and not row["verified"] and not row["dropped"]:
                continue
            conflicts = connection.execute(
                "SELECT COUNT(*) FROM pair_labels WHERE statute_key=? AND label='CONFLICT'",
                (statute_key,),
            ).fetchone()[0]
            sc_row = connection.execute(
                """SELECT COUNT(DISTINCT j.id) AS scanned,
                          SUM(CASE WHEN p.id IS NOT NULL THEN 1 ELSE 0 END) AS propositions
                   FROM judgments j JOIN courts c ON c.id=j.court_id
                   LEFT JOIN propositions p ON p.judgment_id=j.id AND p.statute_key=?
                     AND p.verify_status IN ('VERIFIED_EXACT','VERIFIED_FUZZY')
                   WHERE c.level='SC'""",
                (statute_key,),
            ).fetchone()
            if sc_row["propositions"]:
                badge = "SC proposition found in corpus"
            else:
                badge = f"No SC resolution found in {sc_row['scanned']} SC judgments scanned"
            summaries.append({
                "statute_key": statute_key, "display_name": display_name,
                "total_judgments": int(row["judgments"] or 0),
                "verified_propositions": int(row["verified"] or 0),
                "dropped_hallucinations": int(row["dropped"] or 0),
                "conflict_count": int(conflicts), "sc_status_badge": badge,
            })
    return summaries


@app.get("/api/statutes/{statute_key}/graph", response_model=StatuteGraphResponse)
def statute_graph(statute_key: str) -> dict[str, Any]:
    _validate_statute(statute_key)
    with db_connection() as connection:
        sc_count = connection.execute(
            "SELECT COUNT(DISTINCT j.id) FROM judgments j JOIN courts c ON c.id=j.court_id WHERE c.level='SC'"
        ).fetchone()[0]
        node_rows = connection.execute(
            """SELECT p.id, j.id AS judgment_id, j.court_id, c.name AS court_name,
                      c.short_code AS court_short, c.level, j.title AS judgment_title,
                      j.cnr, j.decision_date, p.holding AS holding_preview,
                      j.s3_uri, j.local_pdf_path
               FROM propositions p JOIN judgments j ON j.id=p.judgment_id
               JOIN courts c ON c.id=j.court_id
               WHERE p.statute_key=? AND p.verify_status IN ('VERIFIED_EXACT','VERIFIED_FUZZY')
               ORDER BY j.decision_date""",
            (statute_key,),
        ).fetchall()
        edge_rows = connection.execute(
            """SELECT id, prop_a_id, prop_b_id, label, confidence, reason, sc_status
               FROM pair_labels WHERE statute_key=?
                 AND label IN ('CONFLICT','AGREE','DISTINGUISHABLE_ON_FACTS')""",
            (statute_key,),
        ).fetchall()
    return {
        "statute_key": statute_key, "display_name": STATUTE_NAMES[statute_key],
        "sc_scanned_count": int(sc_count),
        "nodes": [_graph_node(row) for row in node_rows],
        "edges": [
            {
                "id": row["id"], "source": row["prop_a_id"], "target": row["prop_b_id"],
                "label": row["label"], "confidence": row["confidence"],
                "reason": row["reason"], "sc_status": row["sc_status"],
            }
            for row in edge_rows
        ],
    }


@app.get("/api/conflicts/{conflict_id}", response_model=ConflictDetailResponse)
def conflict_detail(conflict_id: str) -> dict[str, Any]:
    with db_connection() as connection:
        pair = connection.execute(
            "SELECT * FROM pair_labels WHERE id=?", (conflict_id,)
        ).fetchone()
        if pair is None:
            raise HTTPException(status_code=404, detail="Conflict edge not found")
        prop_a = _evidence(connection, pair["prop_a_id"])
        prop_b = _evidence(connection, pair["prop_b_id"])
        sc_prop = _evidence(connection, pair["sc_prop_id"]) if pair["sc_prop_id"] else None
    return {
        "conflict_id": pair["id"], "statute_key": pair["statute_key"],
        "label": pair["label"], "reason": pair["reason"],
        "votes": json.loads(pair["votes_json"]), "confidence": pair["confidence"],
        "candidate_score": pair["candidate_score"], "sc_status": pair["sc_status"],
        "prop_a": prop_a, "prop_b": prop_b, "sc_prop": sc_prop,
    }


@app.get("/api/evidence/{proposition_id}", response_model=PropositionEvidence)
def proposition_evidence(proposition_id: str) -> dict[str, Any]:
    with db_connection() as connection:
        evidence = _evidence(connection, proposition_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Proposition not found")
    return evidence


@app.get("/api/evidence/{proposition_id}/page.png")
def evidence_page(proposition_id: str) -> FileResponse:
    with db_connection() as connection:
        row = connection.execute(
            "SELECT j.local_pdf_path, p.page, p.char_start, p.char_end FROM propositions p JOIN judgments j ON j.id=p.judgment_id WHERE p.id=?",
            (proposition_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Proposition not found")
    pdf_path = resolve_path(row["local_pdf_path"])
    if not pdf_path.is_file():
        raise HTTPException(status_code=404, detail="Source PDF is unavailable")
    if pdf_path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=422, detail="This source record has no PDF page image.")
    try:
        image_path = render_highlighted_page(
            pdf_path, row["page"], row["char_start"], row["char_end"]
        )
    except (ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return FileResponse(image_path, media_type="image/png", filename=image_path.name)


@app.post("/api/ingest", status_code=202)
async def ingest(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    court_id: str = Form("UPLOAD"),
) -> dict[str, str]:
    if Path(file.filename or "").suffix.lower() != ".pdf":
        raise HTTPException(status_code=415, detail="Only PDF files are accepted")
    if court_id != "UPLOAD":
        with db_connection() as connection:
            court = connection.execute(
                "SELECT level FROM courts WHERE id=?", (court_id,)
            ).fetchone()
        if court is None or court["level"] != "HC":
            raise HTTPException(
                status_code=422,
                detail="court_id must identify a known High Court, or be omitted for an unverified upload.",
            )
    run_id = str(uuid.uuid4())
    safe_filename = f"{uuid.uuid4().hex}-{Path(file.filename or 'upload.pdf').name}"
    destination = INBOX_DIR / safe_filename
    try:
        content = await file.read()
        if not content.startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="Uploaded file is not a valid PDF")
        destination.write_bytes(content)
        create_run(run_id, "upload", file.filename)
        background_tasks.add_task(
            _ingest_pdf, destination, file.filename or safe_filename, run_id, court_id
        )
    except HTTPException:
        raise
    except OSError as error:
        raise HTTPException(status_code=500, detail=f"Could not save uploaded PDF: {error}") from error
    finally:
        await file.close()
    return {"run_id": run_id}


@app.post("/api/ingest/batch", status_code=202)
async def ingest_batch(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    court_id: str = Form("UPLOAD"),
) -> dict[str, list[str]]:
    if not files:
        raise HTTPException(status_code=400, detail="At least one PDF is required")
    if court_id != "UPLOAD":
        with db_connection() as connection:
            court = connection.execute(
                "SELECT level FROM courts WHERE id=?", (court_id,)
            ).fetchone()
        if court is None or court["level"] != "HC":
            raise HTTPException(
                status_code=422,
                detail="court_id must identify a known High Court, or be omitted for an unverified upload.",
            )

    uploads: list[tuple[UploadFile, str, bytes]] = []
    try:
        for file in files:
            filename = file.filename or "upload.pdf"
            if Path(filename).suffix.lower() != ".pdf":
                raise HTTPException(status_code=415, detail=f"Only PDF files are accepted: {filename}")
            content = await file.read()
            if not content.startswith(b"%PDF-"):
                raise HTTPException(status_code=400, detail=f"Uploaded file is not a valid PDF: {filename}")
            uploads.append((file, filename, content))

        run_ids: list[str] = []
        for _, filename, content in uploads:
            run_id = str(uuid.uuid4())
            safe_filename = f"{uuid.uuid4().hex}-{Path(filename).name}"
            destination = INBOX_DIR / safe_filename
            destination.write_bytes(content)
            create_run(run_id, "upload", filename)
            background_tasks.add_task(_ingest_pdf, destination, filename, run_id, court_id)
            run_ids.append(run_id)
        return {"run_ids": run_ids}
    except HTTPException:
        raise
    except OSError as error:
        raise HTTPException(status_code=500, detail=f"Could not save uploaded PDF: {error}") from error
    finally:
        for file in files:
            await file.close()


@app.post("/api/demo/trigger-live-sim", status_code=202)
def trigger_live_sim(background_tasks: BackgroundTasks) -> dict[str, str]:
    run_id = str(uuid.uuid4())
    create_run(run_id, "live-simulation", "deterministic-live-simulation.pdf")
    background_tasks.add_task(_run_live_simulation, run_id)
    return {"run_id": run_id}


@app.get("/api/runs")
def runs() -> list[dict[str, Any]]:
    with db_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM runs ORDER BY started_at DESC, id DESC"
        ).fetchall()
    return [
        {
            "id": row["id"],
            "kind": row["kind"],
            "filename": row["filename"],
            "status": row["status"],
            "started_at": row["started_at"],
            "ended_at": row["ended_at"],
            "events": json.loads(row["events_json"]),
            "metrics": json.loads(row["metrics_json"]),
        }
        for row in rows
    ]


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str) -> dict[str, Any]:
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "id": run["id"],
        "kind": run["kind"],
        "filename": run["filename"],
        "status": run["status"],
        "started_at": run["started_at"],
        "ended_at": run["ended_at"],
        "events": json.loads(run["events_json"]),
        "metrics": json.loads(run["metrics_json"]),
    }


@app.get("/api/runs/{run_id}/events")
async def run_events(run_id: str) -> EventSourceResponse:
    if get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")

    async def stream():
        sent = 0
        while True:
            run = get_run(run_id)
            if run is None:
                return
            events = get_run_events(run_id) or []
            while sent < len(events):
                yield {"event": "node", "data": json.dumps(events[sent])}
                sent += 1
            if run["ended_at"]:
                yield {"event": "complete", "data": json.dumps({"status": run["status"]})}
                return
            await asyncio.sleep(0.4)

    return EventSourceResponse(stream(), ping=15)


@app.get("/api/eval/summary", response_model=EvalMetricsResponse)
def eval_summary() -> dict[str, Any]:
    return calculate_metrics()


@app.get("/api/briefs/{statute_key}.pdf")
def statute_brief(statute_key: str) -> FileResponse:
    _validate_statute(statute_key)
    from backend.brief_generator import generate_forum_risk_brief

    path = generate_forum_risk_brief(statute_key)
    return FileResponse(path, media_type="application/pdf", filename=path.name)
