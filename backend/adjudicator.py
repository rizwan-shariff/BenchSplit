import json
import re
import uuid
from typing import Any

from pydantic import ValidationError

from backend.db import db_connection
from backend.llm_client import request_json
from backend.models import LLMAdjudicationOutput

LABELS = ("CONFLICT", "AGREE", "DISTINGUISHABLE_ON_FACTS", "UNRELATED")


def _majority_vote(votes: list[tuple[str, str]]) -> tuple[str, str, float]:
    labels = [label for label, _ in votes]
    label = max(LABELS, key=labels.count)
    reason = next(reason for vote_label, reason in votes if vote_label == label)
    return label, reason, labels.count(label) / len(labels)


def _rule_label(holding_a: str, holding_b: str) -> tuple[str, str]:
    words_a = set(re.findall(r"\w+", holding_a.lower()))
    words_b = set(re.findall(r"\w+", holding_b.lower()))
    opposition = ({"must", "mandatory", "shall"} & words_a and {"may", "discretionary", "directory"} & words_b) or (
        {"must", "mandatory", "shall"} & words_b and {"may", "discretionary", "directory"} & words_a
    )
    if opposition:
        return (
            "CONFLICT",
            "Holding A uses a mandatory rule while Holding B permits discretion, so they give opposite answers to the same legal question.",
        )
    overlap = len(words_a & words_b) / max(1, len(words_a | words_b))
    if overlap >= 0.35:
        return (
            "AGREE",
            "The holdings use materially overlapping language and reach the same legal rule on the question being compared.",
        )
    return (
        "DISTINGUISHABLE_ON_FACTS",
        "The holdings do not state opposite legal rules; the difference is treated as dependent on the facts or procedural setting described in each source.",
    )


def _one_vote(holding_a: str, holding_b: str, temperature: float) -> tuple[str, str]:
    fallback_label, fallback_reason = _rule_label(holding_a, holding_b)
    result, _ = request_json(
        "Compare two verified legal holdings on the same question. Return JSON with label "
        "CONFLICT, AGREE, DISTINGUISHABLE_ON_FACTS, or UNRELATED and a concise, "
        "evidence-grounded reason. Explicitly state what differs or overlaps between "
        "Holding A and Holding B. Do not invent facts or citations.\n"
        f"Holding A: {holding_a}\nHolding B: {holding_b}",
        {"label": fallback_label, "reason": fallback_reason},
        temperature,
    )
    try:
        adjudication = LLMAdjudicationOutput.model_validate(result)
    except ValidationError:
        adjudication = LLMAdjudicationOutput(
            label=fallback_label,
            reason=fallback_reason,
        )
    return adjudication.label, adjudication.reason


def adjudicate_pair(
    holding_a: str, holding_b: str, statute_key: str, cluster_id: str,
    prop_a_id: str, prop_b_id: str, candidate_score: float,
) -> dict[str, Any]:
    first_vote = _one_vote(holding_a, holding_b, 0.0)
    vote_results = [first_vote]
    if first_vote[0] == "CONFLICT":
        vote_results.extend(
            _one_vote(holding_a, holding_b, 0.4) for _ in range(2)
        )
    label, reason, confidence = _majority_vote(vote_results)
    votes = [vote_label for vote_label, _ in vote_results]
    with db_connection() as connection:
        sc_count = connection.execute(
            "SELECT COUNT(DISTINCT j.id) FROM judgments j JOIN courts c ON c.id=j.court_id WHERE c.level='SC'"
        ).fetchone()[0]
        sc_prop = connection.execute(
            """SELECT p.id FROM cluster_members cm JOIN propositions p ON p.id=cm.proposition_id
               JOIN judgments j ON j.id=p.judgment_id JOIN courts c ON c.id=j.court_id
               WHERE cm.cluster_id=? AND p.statute_key=? AND c.level='SC' LIMIT 1""",
            (cluster_id, statute_key),
        ).fetchone()
        sc_status = (
            "SC proposition found in this question cluster"
            if sc_prop
            else f"No SC resolution found in {sc_count} SC judgments scanned"
        )
        pair_id = str(uuid.uuid4())
        connection.execute(
            """INSERT INTO pair_labels
               (id, statute_key, cluster_id, prop_a_id, prop_b_id, candidate_score, label,
                reason, votes_json, confidence, sc_status, sc_prop_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (pair_id, statute_key, cluster_id, prop_a_id, prop_b_id, candidate_score,
             label, reason, json.dumps(votes), confidence, sc_status, sc_prop["id"] if sc_prop else None),
        )
    return {
        "id": pair_id, "label": label, "reason": reason, "votes": votes,
        "confidence": confidence, "sc_status": sc_status,
    }
