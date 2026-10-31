import type {
  ConflictDetailResponse,
  CourtSummary,
  EvalMetricsResponse,
  HealthResponse,
  PropositionEvidence,
  RunEvent,
  RunSummary,
  StatuteGraphResponse,
  StatuteSummary,
} from "../types/api";

export const API_BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(
      `${response.status} ${response.statusText}${body ? `: ${body}` : ""}`,
    );
  }
  return (await response.json()) as T;
}

async function requestBlob(path: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(
      `${response.status} ${response.statusText}${body ? `: ${body}` : ""}`,
    );
  }
  return response.blob();
}

export const getHealth = (signal?: AbortSignal) =>
  request<HealthResponse>("/health", { signal });

export const getStatutes = (signal?: AbortSignal) =>
  request<StatuteSummary[]>("/statutes", { signal });

export const getCourts = (signal?: AbortSignal) =>
  request<CourtSummary[]>("/courts", { signal });

export const getStatuteGraph = (statuteKey: string, signal?: AbortSignal) =>
  request<StatuteGraphResponse>(
    `/statutes/${encodeURIComponent(statuteKey)}/graph`,
    { signal },
  );

export const getConflict = (conflictId: string, signal?: AbortSignal) =>
  request<ConflictDetailResponse>(
    `/conflicts/${encodeURIComponent(conflictId)}`,
    { signal },
  );

export const getEvidence = (
  propositionId: string,
  signal?: AbortSignal,
) =>
  request<PropositionEvidence>(
    `/evidence/${encodeURIComponent(propositionId)}`,
    { signal },
  );

export const getEvaluation = (signal?: AbortSignal) =>
  request<EvalMetricsResponse>("/eval/summary", { signal });

export const getRuns = (signal?: AbortSignal) =>
  request<RunSummary[]>("/runs", { signal });

export const getRun = (runId: string, signal?: AbortSignal) =>
  request<RunSummary>(`/runs/${encodeURIComponent(runId)}`, { signal });

export async function uploadJudgment(
  file: File,
  courtId = "UPLOAD",
): Promise<{ run_id: string }> {
  const form = new FormData();
  form.append("file", file);
  form.append("court_id", courtId);
  return request<{ run_id: string }>("/ingest", {
    method: "POST",
    body: form,
  });
}

export async function uploadJudgments(
  files: File[],
  courtId = "UPLOAD",
): Promise<{ run_ids: string[] }> {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  form.append("court_id", courtId);
  return request<{ run_ids: string[] }>("/ingest/batch", {
    method: "POST",
    body: form,
  });
}

export const getBrief = (statuteKey: string) =>
  requestBlob(`/briefs/${encodeURIComponent(statuteKey)}.pdf`);

export function evidencePageUrl(proposition: PropositionEvidence): string {
  return proposition.page_image_url;
}

export function subscribeToRun(
  runId: string,
  onEvent: (event: RunEvent) => void,
  onComplete: (status: string) => void,
  onError: (error: Error) => void,
): EventSource {
  const source = new EventSource(
    `${API_BASE}/runs/${encodeURIComponent(runId)}/events`,
  );
  source.addEventListener("node", (event: MessageEvent<string>) => {
    try {
      const payload: unknown = JSON.parse(event.data);
      if (!isRunEvent(payload)) {
        throw new Error("Run event stream returned an invalid event.");
      }
      onEvent(payload);
    } catch (error) {
      source.close();
      onError(
        error instanceof Error
          ? error
          : new Error("Run event stream returned invalid JSON."),
      );
    }
  });
  source.addEventListener("complete", (event: MessageEvent<string>) => {
    try {
      const payload: unknown = JSON.parse(event.data);
      if (!isRecord(payload) || typeof payload.status !== "string") {
        throw new Error("Run completion stream returned an invalid status.");
      }
      onComplete(payload.status);
    } catch (error) {
      onError(
        error instanceof Error
          ? error
          : new Error("Run completion stream returned invalid JSON."),
      );
    } finally {
      source.close();
    }
  });
  source.onerror = () => {
    source.close();
    onError(new Error("Connection to the run event stream was lost."));
  };
  return source;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isRunEvent(value: unknown): value is RunEvent {
  return (
    isRecord(value) &&
    typeof value.node === "string" &&
    typeof value.status === "string" &&
    typeof value.detail === "string" &&
    typeof value.retry === "number" &&
    typeof value.timestamp === "string"
  );
}
