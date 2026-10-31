import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any

import numpy as np

LOGGER = logging.getLogger(__name__)
MODEL_NAME = "all-MiniLM-L6-v2"


@dataclass(frozen=True)
class CandidatePair:
    proposition_a: dict[str, Any]
    proposition_b: dict[str, Any]
    cluster_label: int
    score: float


class EmbeddingEncoder:
    def __init__(self) -> None:
        self._model = None
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                MODEL_NAME, model_kwargs={"local_files_only": True}
            )
        except (ImportError, OSError, ValueError, RuntimeError) as error:
            LOGGER.info("MiniLM weights unavailable; using deterministic TF-IDF fallback: %s", error)

    def encode(self, texts: list[str]) -> np.ndarray:
        if self._model is not None:
            return np.asarray(self._model.encode(texts, normalize_embeddings=True), dtype=float)
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer

            vectorizer = TfidfVectorizer(
                ngram_range=(1, 2), lowercase=True, token_pattern=r"(?u)\b\w+\b"
            )
            matrix = vectorizer.fit_transform(texts)
            return matrix.toarray().astype(float)
        except (ImportError, ValueError):
            vocabulary: dict[str, int] = {}
            token_rows = [re.findall(r"\w+", text.lower()) for text in texts]
            for tokens in token_rows:
                for token in tokens:
                    vocabulary.setdefault(token, len(vocabulary))
            matrix = np.zeros((len(texts), len(vocabulary)), dtype=float)
            for row, tokens in enumerate(token_rows):
                for token in tokens:
                    matrix[row, vocabulary[token]] += 1
            return _normalize_rows(matrix)


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.where(norms == 0, 1, norms)


def _cluster_labels(embeddings: np.ndarray, threshold: float) -> np.ndarray:
    count = len(embeddings)
    if count < 2:
        return np.zeros(count, dtype=int)
    try:
        from sklearn.cluster import AgglomerativeClustering

        model = AgglomerativeClustering(
            n_clusters=None, distance_threshold=threshold, metric="cosine", linkage="average"
        )
        return model.fit_predict(embeddings)
    except (ImportError, TypeError, ValueError):
        labels = np.full(count, -1, dtype=int)
        next_label = 0
        for index in range(count):
            if labels[index] >= 0:
                continue
            labels[index] = next_label
            similarities = embeddings[index] @ embeddings.T
            labels[(similarities >= 1.0 - threshold) & (labels < 0)] = next_label
            next_label += 1
        return labels


def cluster_and_rank(
    propositions: list[dict[str, Any]], courts: dict[str, dict[str, Any]],
    threshold: float = 0.35, top_k: int = 3,
) -> tuple[np.ndarray, list[CandidatePair], np.ndarray, np.ndarray]:
    if not propositions:
        return np.array([], dtype=int), [], np.empty((0, 0)), np.empty((0, 0))
    encoder = EmbeddingEncoder()
    questions = [str(prop["question"]) for prop in propositions]
    holdings = [str(prop["holding"]) for prop in propositions]
    q_embeddings = encoder.encode(questions)
    h_embeddings = encoder.encode(holdings)
    labels = _cluster_labels(q_embeddings, threshold)
    candidates: list[CandidatePair] = []
    for cluster_label in sorted(set(int(label) for label in labels)):
        indices = [i for i, label in enumerate(labels) if int(label) == cluster_label]
        cluster_candidates: list[CandidatePair] = []
        for position, left_index in enumerate(indices):
            left = propositions[left_index]
            left_court = courts.get(str(left.get("court_id")), {})
            if left_court.get("level") != "HC":
                continue
            for right_index in indices[position + 1:]:
                right = propositions[right_index]
                right_court = courts.get(str(right.get("court_id")), {})
                if right_court.get("level") != "HC" or left.get("court_id") == right.get("court_id"):
                    continue
                q_cosine = float(np.dot(q_embeddings[left_index], q_embeddings[right_index]) /
                                 max(1e-12, np.linalg.norm(q_embeddings[left_index]) * np.linalg.norm(q_embeddings[right_index])))
                h_cosine = float(np.dot(h_embeddings[left_index], h_embeddings[right_index]) /
                                 max(1e-12, np.linalg.norm(h_embeddings[left_index]) * np.linalg.norm(h_embeddings[right_index])))
                cluster_candidates.append(CandidatePair(left, right, cluster_label, q_cosine - h_cosine))
        candidates.extend(sorted(cluster_candidates, key=lambda pair: pair.score, reverse=True)[:top_k])
    return labels, candidates, q_embeddings, h_embeddings


def cluster_statute_and_adjudicate(statute_key: str) -> int:
    from backend.adjudicator import adjudicate_pair
    from backend.db import db_connection

    with db_connection() as connection:
        rows = connection.execute(
            """SELECT p.*, j.court_id, j.cnr, c.level
               FROM propositions p JOIN judgments j ON j.id=p.judgment_id
               JOIN courts c ON c.id=j.court_id
               WHERE p.statute_key=? AND p.verify_status IN ('VERIFIED_EXACT','VERIFIED_FUZZY')
                 AND j.court_id<>'UPLOAD'
               ORDER BY p.id""",
            (statute_key,),
        ).fetchall()
    propositions = [dict(row) for row in rows]
    if not propositions:
        return 0
    courts = {
        str(row["court_id"]): {"level": row["level"]}
        for row in propositions
    }
    labels, candidates, q_embeddings, h_embeddings = cluster_and_rank(propositions, courts)
    cluster_ids = {
        int(label): f"CL-{statute_key}-{uuid.uuid4().hex[:12]}"
        for label in sorted(set(int(value) for value in labels))
    }
    with db_connection() as connection:
        for index, proposition in enumerate(propositions):
            connection.execute(
                "UPDATE propositions SET embedding_q=?, embedding_h=? WHERE id=?",
                (
                    np.asarray(q_embeddings[index], dtype=np.float32).tobytes(),
                    np.asarray(h_embeddings[index], dtype=np.float32).tobytes(),
                    proposition["id"],
                ),
            )
        for label, cluster_id in cluster_ids.items():
            members = [
                proposition for index, proposition in enumerate(propositions)
                if int(labels[index]) == label
            ]
            connection.execute(
                """INSERT INTO clusters (id, statute_key, canonical_question, method, threshold)
                   VALUES (?, ?, ?, 'agglomerative_cosine', 0.35)""",
                (cluster_id, statute_key, members[0]["question"]),
            )
            connection.executemany(
                "INSERT INTO cluster_members (cluster_id, proposition_id) VALUES (?, ?)",
                [(cluster_id, proposition["id"]) for proposition in members],
            )
        existing_pairs = {
            tuple(sorted((row["prop_a_id"], row["prop_b_id"])))
            for row in connection.execute(
                "SELECT prop_a_id, prop_b_id FROM pair_labels WHERE statute_key=?",
                (statute_key,),
            )
        }
    indexed = {str(proposition["id"]): index for index, proposition in enumerate(propositions)}
    for uploaded in (
        proposition for proposition in propositions
        if str(proposition.get("cnr", "")).startswith("UPLOAD")
    ):
        uploaded_id = str(uploaded["id"])
        uploaded_index = indexed[uploaded_id]
        uploaded_court = str(uploaded["court_id"])
        closest: tuple[float, dict[str, Any], int] | None = None
        for counterpart_index, counterpart in enumerate(propositions):
            if (
                counterpart_index == uploaded_index
                or str(counterpart["court_id"]) == uploaded_court
                or courts.get(str(counterpart.get("court_id")), {}).get("level") != "HC"
            ):
                continue
            pair_key = tuple(sorted((uploaded_id, str(counterpart["id"]))))
            if pair_key in existing_pairs:
                continue
            question_score = float(
                np.dot(q_embeddings[uploaded_index], q_embeddings[counterpart_index])
                / max(
                    1e-12,
                    np.linalg.norm(q_embeddings[uploaded_index])
                    * np.linalg.norm(q_embeddings[counterpart_index]),
                )
            )
            if closest is None or question_score > closest[0]:
                closest = (question_score, counterpart, counterpart_index)
        if closest is not None:
            question_score, counterpart, counterpart_index = closest
            candidates.append(
                CandidatePair(
                    uploaded,
                    counterpart,
                    int(labels[uploaded_index]),
                    question_score - float(
                        np.dot(h_embeddings[uploaded_index], h_embeddings[counterpart_index])
                        / max(
                            1e-12,
                            np.linalg.norm(h_embeddings[uploaded_index])
                            * np.linalg.norm(h_embeddings[counterpart_index]),
                        )
                    ),
                )
            )
    inserted = 0
    for candidate in candidates:
        left, right = candidate.proposition_a, candidate.proposition_b
        pair_key = tuple(sorted((str(left["id"]), str(right["id"]))))
        if pair_key in existing_pairs:
            continue
        adjudicate_pair(
            str(left["holding"]), str(right["holding"]), statute_key,
            cluster_ids[candidate.cluster_label], str(left["id"]), str(right["id"]),
            candidate.score,
        )
        inserted += 1
    return inserted
