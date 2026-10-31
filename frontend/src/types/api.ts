export type AdjudicationLabel =
  | "CONFLICT"
  | "AGREE"
  | "DISTINGUISHABLE_ON_FACTS"
  | "UNRELATED";

export interface HealthResponse {
  status: string;
  llm_provider: string;
  dataset_mode: "empty" | "synthetic-test" | "mixed" | "ingested" | string;
}

export interface RunEvent {
  node: string;
  status: string;
  detail: string;
  retry: number;
  timestamp: string;
}

export interface RunSummary {
  id: string;
  kind: string;
  filename: string | null;
  status: "queued" | "running" | "completed" | "failed" | string;
  started_at: string;
  ended_at: string | null;
  events: RunEvent[];
  metrics: Record<string, number>;
}

export interface StatuteSummary {
  statute_key: string;
  display_name: string;
  total_judgments: number;
  verified_propositions: number;
  dropped_hallucinations: number;
  conflict_count: number;
  sc_status_badge: string;
}

export interface CourtSummary {
  id: string;
  name: string;
  short_code: string;
}

export interface GraphNode {
  id: string;
  court_id: string;
  court_name: string;
  court_short: string;
  level: "HC" | "SC";
  judgment_title: string;
  cnr: string;
  decision_date: string;
  holding_preview: string;
  s3_uri: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label: Exclude<AdjudicationLabel, "UNRELATED">;
  confidence: number;
  reason: string;
  sc_status: string;
}

export interface StatuteGraphResponse {
  statute_key: string;
  display_name: string;
  sc_scanned_count: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface PropositionEvidence {
  proposition_id: string;
  court_name: string;
  judgment_title: string;
  cnr: string;
  decision_date: string;
  s3_uri: string;
  pdf_sha256: string;
  question: string;
  holding: string;
  quote: string;
  page: number;
  char_start: number;
  char_end: number;
  verify_status: string;
  verify_score: number;
  retry_count: number;
  page_image_url: string;
}

export interface ConflictDetailResponse {
  conflict_id: string;
  statute_key: string;
  label: AdjudicationLabel;
  reason: string;
  votes: string[];
  confidence: number;
  candidate_score: number;
  sc_status: string;
  prop_a: PropositionEvidence;
  prop_b: PropositionEvidence;
  sc_prop: PropositionEvidence | null;
}

export interface EvalMetricsResponse {
  total_gold_pairs_test: number;
  precision: number;
  recall: number;
  f1_score: number;
  cohens_kappa: number;
  baseline_f1_score: number;
  f1_improvement_over_baseline: number;
  total_extractions_attempted: number;
  total_extractions_dropped: number;
  hallucination_drop_rate: number;
  confusion_matrix: {
    TP: number;
    FP: number;
    TN: number;
    FN: number;
  };
  conflict_definition: string;
}

export interface IngestResponse {
  run_id: string;
}
