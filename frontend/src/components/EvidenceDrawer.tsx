import { ExternalLink, X } from "lucide-react";
import { Link } from "react-router-dom";
import type { GraphNode, PropositionEvidence } from "../types/api";
import { ApiState, Badge, Button } from "./ui";

interface EvidenceDrawerProps {
  node: GraphNode | null;
  evidence: PropositionEvidence | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}

export default function EvidenceDrawer({
  node,
  evidence,
  loading,
  error,
  onClose,
}: EvidenceDrawerProps) {
  if (!node) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="presentation">
      <button
        type="button"
        className="absolute inset-0 bg-espresso/35"
        onClick={onClose}
        aria-label="Close evidence details"
      />
      <aside
        className="relative flex h-full w-full max-w-[500px] flex-col overflow-y-auto border-l border-[#dfd0bd] bg-paper shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="evidence-drawer-title"
      >
        <div className="sticky top-0 flex items-start justify-between gap-4 border-b border-[#e5d8c8] bg-paper px-5 py-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-brass">
              Source inspection
            </p>
            <h2
              id="evidence-drawer-title"
              className="mt-1 font-editorial text-xl font-semibold text-espresso"
            >
              {node.court_name}
            </h2>
          </div>
          <Button
            variant="ghost"
            className="!min-h-9 !w-9 !p-0"
            onClick={onClose}
            aria-label="Close evidence details"
          >
            <X size={17} />
          </Button>
        </div>

        <div className="space-y-5 p-5">
          <div className="flex flex-wrap gap-2">
            <Badge tone={node.level === "SC" ? "brass" : "blue"}>{node.level}</Badge>
            {evidence ? (
              <Badge tone="success">{evidence.verify_status.replaceAll("_", " ")}</Badge>
            ) : null}
          </div>
          <ApiState loading={loading} error={error} />
          {evidence ? (
            <>
              <section>
                <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted-ink">
                  Judgment
                </p>
                <h3 className="mt-1 text-sm font-semibold text-espresso">{node.judgment_title}</h3>
                <p className="mt-2 text-xs leading-5 text-muted-ink">
                  CNR: <span className="font-mono">{node.cnr}</span>
                  <span className="mx-2">·</span>
                  {node.decision_date}
                </p>
              </section>
              <section className="rounded-lg border border-[#e3d6c6] bg-white/70 p-4">
                <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted-ink">
                  Proposition
                </p>
                <p className="mt-2 text-sm leading-6 text-espresso">{evidence.holding}</p>
              </section>
              <section>
                <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted-ink">
                  Source quotation
                </p>
                <blockquote className="mt-2 border-l-2 border-brass pl-3 font-editorial text-base leading-6 text-espresso">
                  “{evidence.quote}”
                </blockquote>
                <p className="mt-2 text-[10px] text-muted-ink">
                  Source page {evidence.page} · verification score {evidence.verify_score}
                </p>
              </section>
              <div className="flex flex-wrap gap-2 pt-1">
                <Link
                  to={`/judgment/${encodeURIComponent(evidence.proposition_id)}`}
                  className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-espresso bg-espresso px-3.5 py-2 text-sm font-semibold text-white hover:bg-[#44342c]"
                >
                  Open judgment viewer <ExternalLink size={14} />
                </Link>
                <Button variant="secondary" onClick={onClose}>Close panel</Button>
              </div>
            </>
          ) : null}
        </div>
      </aside>
    </div>
  );
}
