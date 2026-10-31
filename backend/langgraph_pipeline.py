import uuid
from typing import Callable, Optional, TypedDict

from backend.config import PROMPT_VERSION
from backend.db import (
    append_run_event,
    create_run,
    db_connection,
    finish_run,
    get_run,
)
from backend.llm_client import check_entailment, extract_proposition
from backend.verifier import verify_quote


class ExtractionState(TypedDict):
    run_id: str
    judgment_id: str
    passage_text: str
    page_num: int
    statute_key: str
    raw_extraction: Optional[dict]
    verify_status: str
    verify_score: float
    char_start: int
    char_end: int
    retry_count: int
    error_feedback: Optional[str]
    entailment_passed: bool
    final_status: str


Extractor = Callable[[ExtractionState], dict]
EntailmentChecker = Callable[[str, str], tuple[bool, str]]


def _record(state: ExtractionState, node: str, status: str, detail: str) -> None:
    append_run_event(state["run_id"], node, status, detail, state["retry_count"])


def _insert_proposition(state: ExtractionState, model_name: str) -> str:
    raw = state.get("raw_extraction") or {}
    proposition_id = str(uuid.uuid4())
    verified = state["final_status"] == "ACCEPTED"
    quote = raw.get("quote", "")
    with db_connection() as connection:
        connection.execute(
            """INSERT INTO propositions
               (id, judgment_id, statute_key, question, holding, quote, page, char_start,
                char_end, verify_status, verify_score, retry_count, entailment_supported,
                model_name, prompt_version)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                proposition_id, state["judgment_id"], state["statute_key"],
                str(raw.get("question", "Legal question extracted from judgment")),
                str(raw.get("holding", "Holding extracted from judgment")), str(quote),
                state["page_num"], max(0, state["char_start"]), max(0, state["char_end"]),
                state["verify_status"] if verified else "DROPPED",
                state["verify_score"], state["retry_count"], int(state["entailment_passed"]),
                model_name, PROMPT_VERSION,
            ),
        )
    return proposition_id


def run_extraction(
    run_id: str,
    judgment_id: str,
    passage_text: str,
    page_num: int,
    statute_key: str,
    page_char_offset: int = 0,
    page_text: Optional[str] = None,
    extractor: Optional[Extractor] = None,
    entailment_checker: Optional[EntailmentChecker] = None,
    complete_run: bool = True,
) -> dict:
    if get_run(run_id) is None:
        create_run(run_id, "extraction")
    state: ExtractionState = {
        "run_id": run_id, "judgment_id": judgment_id, "passage_text": passage_text,
        "page_num": page_num, "statute_key": statute_key, "raw_extraction": None,
        "verify_status": "PENDING", "verify_score": 0.0, "char_start": 0, "char_end": 0,
        "retry_count": 0, "error_feedback": None, "entailment_passed": False, "final_status": "PENDING",
    }
    active_provider = ["rule-based"]

    def extract_node(current: ExtractionState) -> dict:
        if extractor:
            extraction = extractor(current)
            provider = "simulated"
        else:
            extraction, provider = extract_proposition(
                current["passage_text"], current["statute_key"], current["error_feedback"] or ""
            )
        active_provider[0] = provider
        _record(current, "Extract", "running", f"Extraction attempt {current['retry_count'] + 1}")
        return {"raw_extraction": extraction}

    def verify_node(current: ExtractionState) -> dict:
        extraction = current.get("raw_extraction") or {}
        result = verify_quote(
            current["passage_text"], page_char_offset, str(extraction.get("quote", "")),
            page_text=page_text,
        )
        _record(
            current, "Verify", result.status,
            result.error_msg or f"Quote verified with score {result.score:.1f}",
        )
        return {
            "verify_status": result.status, "verify_score": result.score,
            "char_start": result.char_start, "char_end": result.char_end,
            "error_feedback": result.error_msg,
            "raw_extraction": {**extraction, "quote": result.quote},
        }

    def repair_node(current: ExtractionState) -> dict:
        next_retry = current["retry_count"] + 1
        _record(current, "Repair", "triggered", current["error_feedback"] or "Copy a source-contiguous quote.")
        return {"retry_count": next_retry}

    def entailment_node(current: ExtractionState) -> dict:
        extraction = current.get("raw_extraction") or {}
        quote = str(extraction.get("quote", ""))
        holding = str(extraction.get("holding", ""))
        if entailment_checker:
            supported, rationale = entailment_checker(quote, holding)
        else:
            supported, rationale, _ = check_entailment(quote, holding)
        _record(current, "Entailment", "passed" if supported else "failed", rationale)
        return {"entailment_passed": supported}

    def accept_node(current: ExtractionState) -> dict:
        _record(current, "Accept", "accepted", "Evidence verified and entailment supported.")
        return {"final_status": "ACCEPTED"}

    def drop_node(current: ExtractionState) -> dict:
        _record(current, "Drop", "dropped", current.get("error_feedback") or "Entailment did not support the holding.")
        return {"final_status": "DROPPED"}

    def verify_route(current: ExtractionState) -> str:
        if current["verify_status"] in {"VERIFIED_EXACT", "VERIFIED_FUZZY"}:
            return "entailment"
        return "repair" if current["retry_count"] < 2 else "drop"

    def entailment_route(current: ExtractionState) -> str:
        return "accept" if current["entailment_passed"] else "drop"

    try:
        try:
            from langgraph.graph import END, START, StateGraph

            graph = StateGraph(ExtractionState)
            graph.add_node("extract", extract_node)
            graph.add_node("verify", verify_node)
            graph.add_node("repair", repair_node)
            graph.add_node("entailment", entailment_node)
            graph.add_node("accept", accept_node)
            graph.add_node("drop", drop_node)
            graph.add_edge(START, "extract")
            graph.add_edge("extract", "verify")
            graph.add_conditional_edges("verify", verify_route, {
                "entailment": "entailment", "repair": "repair", "drop": "drop",
            })
            graph.add_edge("repair", "extract")
            graph.add_conditional_edges("entailment", entailment_route, {
                "accept": "accept", "drop": "drop",
            })
            graph.add_edge("accept", END)
            graph.add_edge("drop", END)
            state = graph.compile().invoke(state)
        except ImportError:
            while True:
                state.update(extract_node(state))
                state.update(verify_node(state))
                route = verify_route(state)
                if route == "repair":
                    state.update(repair_node(state))
                    continue
                if route == "drop":
                    state.update(drop_node(state))
                    break
                state.update(entailment_node(state))
                state.update(accept_node(state) if state["entailment_passed"] else drop_node(state))
                break
        proposition_id = _insert_proposition(state, active_provider[0])
        state["proposition_id"] = proposition_id  # type: ignore[typeddict-item]
        if complete_run:
            finish_run(run_id, "completed", {"final_status": state["final_status"]})
        return state
    except Exception:
        if complete_run:
            finish_run(run_id, "failed")
        raise
