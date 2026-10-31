from typing import Any

from backend.db import db_connection

CONFLICT_DEFINITION = (
    "A conflict is a material, irreconcilable difference in the legal rule applied to the same "
    "statutory provision and materially similar question; a different outcome alone is insufficient."
)
BASELINE_CONFLICT_SCORE = 0.839


def _binary_confusion(actual: list[bool], predicted: list[bool]) -> dict[str, int]:
    matrix = {"TP": 0, "FP": 0, "TN": 0, "FN": 0}
    for truth, guess in zip(actual, predicted):
        if truth and guess:
            matrix["TP"] += 1
        elif not truth and guess:
            matrix["FP"] += 1
        elif not truth and not guess:
            matrix["TN"] += 1
        else:
            matrix["FN"] += 1
    return matrix


def _precision_recall_f1(matrix: dict[str, int]) -> tuple[float, float, float]:
    precision = matrix["TP"] / max(1, matrix["TP"] + matrix["FP"])
    recall = matrix["TP"] / max(1, matrix["TP"] + matrix["FN"])
    f1 = 2 * precision * recall / max(1e-12, precision + recall)
    return precision, recall, f1


def _cohens_kappa(labels_a: list[str], labels_b: list[str]) -> float:
    if not labels_a:
        return 0.0
    observed = sum(first == second for first, second in zip(labels_a, labels_b)) / len(labels_a)
    categories = set(labels_a) | set(labels_b)
    expected = sum(
        (labels_a.count(category) / len(labels_a)) * (labels_b.count(category) / len(labels_b))
        for category in categories
    )
    return (observed - expected) / (1.0 - expected) if expected < 1 else 1.0


def calculate_metrics() -> dict[str, Any]:
    with db_connection() as connection:
        rows = connection.execute(
            """SELECT g.final_gold_label, g.annotator_1_label, g.annotator_2_label,
                      COALESCE(pl.label, 'AGREE') AS predicted_label,
                      COALESCE(pl.candidate_score, 0.0) AS candidate_score
               FROM gold_pairs g LEFT JOIN pair_labels pl
                 ON ((pl.prop_a_id=g.prop_a_id AND pl.prop_b_id=g.prop_b_id)
                  OR (pl.prop_a_id=g.prop_b_id AND pl.prop_b_id=g.prop_a_id))
               WHERE g.split='test'"""
        ).fetchall()
        all_annotations = connection.execute(
            "SELECT annotator_1_label, annotator_2_label FROM gold_pairs"
        ).fetchall()
        extraction_counts = connection.execute(
            """SELECT COUNT(*) AS attempted,
                      SUM(CASE WHEN verify_status='DROPPED' THEN 1 ELSE 0 END) AS dropped
               FROM propositions"""
        ).fetchone()
    gold = [row["final_gold_label"] == "CONFLICT" for row in rows]
    predicted = [row["predicted_label"] == "CONFLICT" for row in rows]
    confusion = _binary_confusion(gold, predicted)
    precision, recall, f1 = _precision_recall_f1(confusion)
    baseline_predictions = [
        row["candidate_score"] >= BASELINE_CONFLICT_SCORE for row in rows
    ]
    baseline_f1 = _precision_recall_f1(_binary_confusion(gold, baseline_predictions))[2]
    annotator_1 = [row["annotator_1_label"] for row in all_annotations]
    annotator_2 = [row["annotator_2_label"] for row in all_annotations]
    attempted = int(extraction_counts["attempted"] or 0)
    dropped = int(extraction_counts["dropped"] or 0)
    return {
        "total_gold_pairs_test": len(rows),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "cohens_kappa": round(_cohens_kappa(annotator_1, annotator_2), 4),
        "baseline_f1_score": round(baseline_f1, 4),
        "f1_improvement_over_baseline": round(f1 - baseline_f1, 4),
        "total_extractions_attempted": attempted,
        "total_extractions_dropped": dropped,
        "hallucination_drop_rate": round(dropped / attempted, 4) if attempted else 0.0,
        "confusion_matrix": confusion,
        "conflict_definition": CONFLICT_DEFINITION,
    }
