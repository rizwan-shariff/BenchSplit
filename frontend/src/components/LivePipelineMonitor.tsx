import { AlertCircle, Check, LoaderCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { getRun, subscribeToRun } from "../services/api";
import { useApiResource } from "../hooks/useApiResource";
import type { RunEvent } from "../types/api";
import { ApiState, Badge, Card } from "./ui";

interface LivePipelineMonitorProps {
  runId: string | null;
  compact?: boolean;
}

export default function LivePipelineMonitor({
  runId,
  compact = false,
}: LivePipelineMonitorProps) {
  const run = useApiResource(
    runId ?? "",
    (signal) => getRun(runId!, signal),
  );
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [completedStatus, setCompletedStatus] = useState<string | null>(null);

  useEffect(() => {
    setEvents(run.data?.events ?? []);
    setCompletedStatus(null);
    setStreamError(null);
  }, [run.data?.id, run.data?.events]);

  useEffect(() => {
    if (!runId || !run.data || run.data.status !== "running") return;

    const stream = subscribeToRun(
      runId,
      (event) => {
        setEvents((current) =>
          current.some(
            (item) =>
              item.timestamp === event.timestamp &&
              item.node === event.node &&
              item.status === event.status,
          )
            ? current
            : [...current, event],
        );
      },
      (status) => {
        setCompletedStatus(status);
        run.reload();
      },
      (error) => setStreamError(error.message),
    );
    return () => stream.close();
  }, [runId, run.data?.status]);

  const status = completedStatus ?? run.data?.status ?? "unknown";
  const active = status === "running";

  return (
    <Card className={compact ? "p-4" : "p-5"}>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-editorial text-xl font-semibold text-espresso">
            Processing events
          </h2>
          <p className="mt-1 text-xs text-muted-ink">
            {runId ? `Backend run ${runId}` : "No run selected"}
          </p>
        </div>
        {run.data ? <Badge tone={status === "failed" ? "danger" : active ? "brass" : "success"}>{status}</Badge> : null}
      </div>

      <ApiState
        loading={run.loading}
        error={run.error}
        empty={!runId && !run.loading}
        onRetry={run.reload}
      />
      {streamError ? <p className="mt-3 text-xs text-oxblood" role="alert">{streamError}</p> : null}

      {run.data ? (
        events.length ? (
          <ol className={compact ? "space-y-2" : "space-y-3"}>
            {events.map((event, index) => {
              const failed = /fail|error/i.test(event.status);
              const complete = !active || index < events.length - 1;
              return (
                <li
                  key={`${event.timestamp}-${event.node}-${index}`}
                  className="flex items-start gap-3 rounded-lg border border-[#e9dfd3] bg-[#fffaf4] px-3 py-2.5"
                >
                  <span className="mt-0.5 text-brass">
                    {failed ? (
                      <AlertCircle size={16} className="text-oxblood" />
                    ) : complete ? (
                      <Check size={16} className="text-forest" />
                    ) : (
                      <LoaderCircle size={16} className="animate-spin" />
                    )}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-xs font-semibold text-espresso">{event.node} · {event.status}</span>
                    <span className="mt-1 block text-[11px] leading-4 text-muted-ink">{event.detail}</span>
                  </span>
                  <time className="shrink-0 text-[9px] text-muted-ink" dateTime={event.timestamp}>
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </time>
                </li>
              );
            })}
          </ol>
        ) : (
          <p className="rounded-lg border border-[#e9dfd3] bg-[#fffaf4] p-4 text-xs text-muted-ink" role="status">
            {active ? "Waiting for the backend to emit the first pipeline event…" : "This run has no recorded pipeline events."}
          </p>
        )
      ) : null}
      <p className="sr-only" aria-live="polite">
        {active ? "Backend ingestion is running." : run.data ? `Backend run status: ${status}.` : ""}
      </p>
    </Card>
  );
}
