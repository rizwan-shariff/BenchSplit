from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LLMExtractionOutput(StrictModel):
    statute_key: str = Field(description="Normalized key, e.g., 'NI_ACT_S138' or 'ARB_ACT_S11'")
    question: str = Field(description="Single legal question answered by the court in one sentence")
    holding: str = Field(description="The court's affirmative/negative legal ruling on that question")
    quote: str = Field(description="EXACT verbatim substring copied character-for-character from the passage")


class LLMEntailmentOutput(StrictModel):
    supports: bool = Field(description="True ONLY if the verbatim quote directly supports the stated holding")
    rationale: str


class LLMAdjudicationOutput(StrictModel):
    label: Literal["CONFLICT", "AGREE", "DISTINGUISHABLE_ON_FACTS", "UNRELATED"]
    reason: str = Field(description="One-sentence legal explanation comparing Holding A and Holding B")


class StatuteSummary(StrictModel):
    statute_key: str
    display_name: str
    total_judgments: int
    verified_propositions: int
    dropped_hallucinations: int
    conflict_count: int
    sc_status_badge: str


class CourtSummary(StrictModel):
    id: str
    name: str
    short_code: str


class GraphNode(StrictModel):
    id: str
    court_id: str
    court_name: str
    court_short: str
    level: Literal["HC", "SC"]
    judgment_title: str
    cnr: str
    decision_date: str
    holding_preview: str
    s3_uri: str


class GraphEdge(StrictModel):
    id: str
    source: str
    target: str
    label: Literal["CONFLICT", "AGREE", "DISTINGUISHABLE_ON_FACTS"]
    confidence: float
    reason: str
    sc_status: str


class StatuteGraphResponse(StrictModel):
    statute_key: str
    display_name: str
    sc_scanned_count: int
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class PropositionEvidence(StrictModel):
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


class ConflictDetailResponse(StrictModel):
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


class EvalMetricsResponse(StrictModel):
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
    confusion_matrix: dict
    conflict_definition: str
