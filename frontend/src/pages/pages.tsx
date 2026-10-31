import {
  ArrowDownToLine,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  FileText,
  Network,
  Scale,
  ShieldAlert,
  Upload,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import ConflictGraphView from "../components/ConflictGraphView";
import EvidenceDrawer from "../components/EvidenceDrawer";
import LivePipelineMonitor from "../components/LivePipelineMonitor";
import StatuteSelector from "../components/StatuteSelector";
import {
  ApiState,
  Badge,
  Button,
  Card,
  EmptyState,
  LinkButton,
  MetricCard,
  PageHeader,
  SectionTitle,
} from "../components/ui";
import { useApiResource } from "../hooks/useApiResource";
import { formatNumber, formatPercent } from "../lib/utils";
import {
  evidencePageUrl,
  getBrief,
  getConflict,
  getCourts,
  getEvaluation,
  getEvidence,
  getHealth,
  getRun,
  getRuns,
  getStatuteGraph,
  getStatutes,
  uploadJudgments,
} from "../services/api";
import type {
  GraphEdge,
  GraphNode,
  PropositionEvidence,
  RunSummary,
  StatuteGraphResponse,
  StatuteSummary,
} from "../types/api";
import ladyJusticeImage from "../assets/lady-justice.jpg";

function useStatuteSelection(statutes: StatuteSummary[]) {
  const [params, setParams] = useSearchParams();
  const candidate = params.get("statute") ?? params.get("key");
  const selected = statutes.some((statute) => statute.statute_key === candidate)
    ? candidate!
    : statutes[0]?.statute_key ?? "";

  function select(value: string) {
    const next = new URLSearchParams(params);
    next.set("statute", value);
    next.delete("key");
    setParams(next, { replace: true });
  }

  return [selected, select] as const;
}

function StatuteControl({
  value,
  statutes,
  onChange,
}: {
  value: string;
  statutes: StatuteSummary[];
  onChange: (value: string) => void;
}) {
  return (
    <StatuteSelector
      value={value}
      statutes={statutes}
      onChange={onChange}
      className="w-full sm:min-w-[280px] sm:max-w-[430px]"
      label="Current statute"
    />
  );
}

function FirstInvestigationLink({
  statuteKey,
  graph,
  children = "Review conflicts",
}: {
  statuteKey: string;
  graph: StatuteGraphResponse | null;
  children?: string;
}) {
  const edge = graph?.edges.find((item) => item.label === "CONFLICT") ?? graph?.edges[0];
  if (!edge) {
    return (
      <Link
        className="inline-flex items-center gap-1 text-xs font-semibold text-oxblood hover:underline"
        to={`/radar?statute=${encodeURIComponent(statuteKey)}`}
      >
        View court network <ArrowRight size={13} />
      </Link>
    );
  }
  return (
    <Link
      className="inline-flex items-center gap-1 text-xs font-semibold text-oxblood hover:underline"
      to={`/investigation?statute=${encodeURIComponent(statuteKey)}&conflict=${encodeURIComponent(edge.id)}`}
    >
      {children} <ArrowRight size={13} />
    </Link>
  );
}

function SourceType({ uri }: { uri: string }) {
  const isSynthetic = uri.startsWith("demo://synthetic/");
  const isFake = uri.startsWith("fake://FAKE_TEST_DATA/");
  return (
    <Badge tone={isSynthetic || isFake ? "brass" : "neutral"}>
      {isFake ? "FAKE TEST DATA · not legal authority" : isSynthetic ? "Backend test fixture · synthetic" : "Backend source"}
    </Badge>
  );
}

export function LandingPage() {
  const landingRef = useRef<HTMLDivElement>(null);
  const justiceMotionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let frame = 0;
    const updateScrollAnimation = () => {
      const landing = landingRef.current;
      const justiceMotion = justiceMotionRef.current;
      if (!landing || !justiceMotion) return;
      const scrollDistance = Math.max(landing.offsetHeight - window.innerHeight, 1);
      const progress = Math.min(
        1,
        Math.max(0, -landing.getBoundingClientRect().top / scrollDistance),
      );
      justiceMotion.style.setProperty(
        "--justice-zoom",
        (3.2 - 2.36 * progress).toFixed(3),
      );
      justiceMotion.style.setProperty("--justice-y", `${22 + 4 * progress}vh`);
      landing.style.setProperty(
        "--justice-caption-opacity",
        Math.min(1, Math.max(0, (progress - 0.55) / 0.45)).toFixed(3),
      );
    };
    const schedule = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(updateScrollAnimation);
    };
    schedule();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
    };
  }, []);

  return (
    <div
      ref={landingRef}
      className="landing-page relative min-h-[220vh] overflow-clip bg-[#f3e8d5] text-espresso"
    >
      <div className="landing-stage sticky top-0 h-screen overflow-hidden">
        <header className="absolute inset-x-0 top-0 z-20 flex h-[92px] items-center justify-between border-b border-espresso/10 px-14">
          <Link to="/" className="flex items-center gap-3" aria-label="Nyaaychakra home">
            <span className="grid h-11 w-11 place-items-center rounded-full border border-brass/60 text-brass">
              <Scale size={20} strokeWidth={1.6} />
            </span>
            <span>
              <span className="block font-editorial text-lg font-semibold tracking-[0.1em]">
                NYAAYCHAKRA
              </span>
              <span className="mt-0.5 block text-[8px] font-bold uppercase tracking-[0.18em] text-[#816844]">
                The precedent desk
              </span>
            </span>
          </Link>
          <Link
            to="/system-health"
            className="text-[10px] font-semibold uppercase tracking-[0.15em] text-muted-ink hover:text-oxblood"
          >
            Backend connection status
          </Link>
        </header>

        <main className="relative mx-auto grid min-h-screen max-w-[1680px] grid-cols-[0.96fr_1.12fr_0.92fr] items-center gap-4 px-14 pb-8 pt-[92px]">
          <div className="pointer-events-none absolute inset-0" aria-hidden="true">
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_51%_51%,rgba(208,181,137,0.46)_0%,rgba(243,232,213,0.12)_32%,transparent_66%)]" />
            <div className="absolute left-[31%] top-[9%] h-[82%] w-[42%] rounded-[50%] border border-brass/15" />
            <div className="absolute left-[34%] top-[13%] h-[74%] w-[36%] rounded-[50%] border border-brass/10" />
          </div>

          <section className="relative z-10 max-w-[420px] py-12">
            <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.19em] text-brass">
              <span className="h-px w-7 bg-brass" />
              Law · evidence · perspective
            </p>
            <h1 className="mt-6 font-editorial text-[clamp(3.8rem,5.5vw,5.4rem)] font-medium leading-[0.91] tracking-[-0.045em]">
              Justice,
              <br />
              <span className="text-oxblood">in balance.</span>
            </h1>
            <p className="mt-6 max-w-[360px] text-sm leading-6 text-muted-ink">
              Explore court treatment, compare statutory interpretations, and
              follow each proposition to its source.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <LinkButton to="/overview" variant="primary" className="!min-h-12 !px-5">
                Enter the workspace <ArrowRight size={16} />
              </LinkButton>
            </div>
            <Link
              to="/statutes"
              className="mt-4 inline-flex items-center gap-2 text-xs font-semibold text-oxblood hover:underline"
            >
              <BookOpen size={14} /> Browse the statute explorer
            </Link>
          </section>

          <div className="pointer-events-none relative z-10 min-h-[680px]" aria-hidden="true" />

          <Link
            to="/overview"
            aria-label="Enter the workspace through the Lady Justice illustration"
            className="landing-justice-link pointer-events-none absolute left-1/2 top-1/2 z-[5] flex h-[88vh] max-h-[900px] w-[min(47vw,720px)] -translate-x-1/2 -translate-y-[64%] items-center justify-center focus-visible:rounded-xl"
          >
            <div
              ref={justiceMotionRef}
              className="landing-justice-motion pointer-events-none absolute inset-0"
            >
              <img
                src={ladyJusticeImage}
                alt="Blindfolded Lady Justice holding scales and a sword"
                className="landing-justice-image pointer-events-auto relative z-10 h-full w-full cursor-pointer object-contain mix-blend-multiply"
              />
            </div>
          </Link>

          <aside className="relative z-10 ml-auto w-full max-w-[310px] py-12">
            <p className="text-[9px] font-bold uppercase tracking-[0.18em] text-brass">
              A clearer path through precedent
            </p>
            <div className="mt-5 space-y-0">
              {[
                {
                  number: "01",
                  title: "Explore the statute",
                  detail: "Start from the provision at the heart of your research.",
                  icon: BookOpen,
                  to: "/statutes",
                },
                {
                  number: "02",
                  title: "Compare perspectives",
                  detail: "Inspect court positions and their connected records.",
                  icon: Network,
                  to: "/radar",
                },
                {
                  number: "03",
                  title: "Trace the evidence",
                  detail: "Follow propositions to the source document.",
                  icon: ShieldAlert,
                  to: "/evidence",
                },
              ].map(({ number, title, detail, icon: Icon, to }) => (
                <Link
                  className="flex gap-3 border-b border-espresso/10 py-4 last:border-b-0"
                  key={number}
                  to={to}
                >
                  <span className="pt-1 font-mono text-[9px] text-brass">{number}</span>
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-brass/25 bg-paper/50 text-brass">
                    <Icon size={15} strokeWidth={1.7} />
                  </span>
                  <span>
                    <span className="block text-xs font-semibold text-espresso">{title}</span>
                    <span className="mt-1 block text-[10px] leading-4 text-muted-ink">{detail}</span>
                  </span>
                </Link>
              ))}
            </div>
          </aside>
        </main>
        <p className="landing-justice-caption pointer-events-none absolute bottom-10 left-1/2 z-20 -translate-x-1/2 whitespace-nowrap text-center font-editorial text-sm italic tracking-wide text-[#715d43]">
          Fiat justitia <span className="mx-2 text-brass/60">·</span> Let justice be done
        </p>
        <div className="pointer-events-none absolute bottom-5 left-14 right-14 z-20 flex items-center justify-between text-[9px] uppercase tracking-[0.13em] text-[#88765d]">
          <span>Independent · considered · source-aware</span>
          <span>Nyaaychakra · Judicial intelligence</span>
        </div>
      </div>
    </div>
  );
}

export function OverviewPage() {
  const statutes = useApiResource("statutes", getStatutes);
  const runs = useApiResource("runs", getRuns);
  const firstStatuteKey = statutes.data?.[0]?.statute_key ?? "";
  const firstGraph = useApiResource(
    firstStatuteKey,
    (signal) => getStatuteGraph(firstStatuteKey, signal),
  );

  const totals = (statutes.data ?? []).reduce(
    (result, item) => ({
      judgments: result.judgments + item.total_judgments,
      propositions: result.propositions + item.verified_propositions,
      conflicts: result.conflicts + item.conflict_count,
    }),
    { judgments: 0, propositions: 0, conflicts: 0 },
  );

  return (
    <>
      <PageHeader
        eyebrow="Workspace overview"
        title="A considered view of the corpus."
        description="Live counts and research records retrieved from the BenchSplit API."
        actions={<LinkButton to="/statutes" variant="primary">Open statute explorer <ArrowRight size={15} /></LinkButton>}
      />
      <ApiState loading={statutes.loading} error={statutes.error} onRetry={statutes.reload} />
      {statutes.data ? (
        <>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Statutory topics" value={String(statutes.data.length)} note="Returned by backend" icon="menu_book" />
            <MetricCard label="Judgments indexed" value={formatNumber(totals.judgments)} note="Current corpus total" icon="account_balance" tone="neutral" />
            <MetricCard label="Conflict signals" value={String(totals.conflicts)} note="Backend adjudication records" icon="compare_arrows" tone="red" />
            <MetricCard label="Verified propositions" value={formatNumber(totals.propositions)} note="Backend-verified records" icon="fact_check" tone="green" />
          </div>
          <div className="mt-6 grid gap-5 xl:grid-cols-[1.25fr_0.75fr]">
            <Card className="p-5">
              <SectionTitle title="Statutory research desk" description="Counts come from the connected corpus." action={<Link to="/radar" className="text-xs font-semibold text-oxblood hover:underline">Open radar →</Link>} />
              {statutes.data.length ? (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[620px] border-collapse text-left">
                    <thead>
                      <tr className="border-b border-[#e7dbce] text-[10px] uppercase tracking-[0.1em] text-muted-ink">
                        <th className="py-3 pr-4 font-semibold">Statutory topic</th>
                        <th className="py-3 pr-4 font-semibold">Judgments</th>
                        <th className="py-3 pr-4 font-semibold">Conflicts</th>
                        <th className="py-3 font-semibold">Next step</th>
                      </tr>
                    </thead>
                    <tbody>
                      {statutes.data.map((statute) => (
                        <tr className="border-b border-[#f0e8df] last:border-0" key={statute.statute_key}>
                          <td className="py-4 pr-4">
                            <Link to={`/statutes?statute=${encodeURIComponent(statute.statute_key)}`} className="text-xs font-semibold text-espresso hover:text-oxblood">{statute.display_name}</Link>
                            <p className="mt-1 font-mono text-[9px] text-muted-ink">{statute.statute_key}</p>
                          </td>
                          <td className="py-4 pr-4 text-xs text-muted-ink">{formatNumber(statute.total_judgments)}</td>
                          <td className="py-4 pr-4"><Badge tone="danger">{statute.conflict_count}</Badge></td>
                          <td className="py-4"><FirstInvestigationLink statuteKey={statute.statute_key} graph={firstGraph.data?.statute_key === statute.statute_key ? firstGraph.data : null} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <EmptyState title="No statutory data" description="The backend returned no statute records." icon="menu_book" />}
            </Card>
            <Card className="p-5">
              <SectionTitle title="Recent ingestion runs" action={<Link to="/runs" className="text-xs font-semibold text-oxblood hover:underline">View all →</Link>} />
              <ApiState loading={runs.loading} error={runs.error} onRetry={runs.reload} empty={runs.data?.length === 0} />
              <div className="space-y-3">
                {runs.data?.slice(0, 5).map((run) => (
                  <Link className="flex items-start justify-between gap-3 border-b border-[#eee5db] pb-3 last:border-0 last:pb-0" key={run.id} to={`/processing?run=${encodeURIComponent(run.id)}`}>
                    <span>
                      <span className="block text-xs font-semibold text-espresso">{run.filename ?? run.id}</span>
                      <span className="mt-1 block text-[10px] text-muted-ink">{run.kind} · {new Date(run.started_at).toLocaleString()}</span>
                    </span>
                    <Badge tone={run.status === "failed" ? "danger" : run.status === "running" ? "brass" : "success"}>{run.status}</Badge>
                  </Link>
                ))}
              </div>
            </Card>
          </div>
          {firstGraph.error ? <p className="mt-4 text-xs text-oxblood" role="alert">Could not load the first statute network: {firstGraph.error}</p> : null}
        </>
      ) : null}
    </>
  );
}

export function StatutesPage() {
  const statutes = useApiResource("statutes", getStatutes);
  const [statuteKey, setStatuteKey] = useStatuteSelection(statutes.data ?? []);
  const [query, setQuery] = useState("");
  const filtered = useMemo(
    () =>
      (statutes.data ?? []).filter((statute) =>
        `${statute.display_name} ${statute.statute_key}`.toLowerCase().includes(query.toLowerCase()),
      ),
    [statutes.data, query],
  );

  return (
    <>
      <PageHeader eyebrow="Workspace · library" title="Statute explorer" description="Browse statutory topics and corpus indicators returned by the backend." />
      <ApiState loading={statutes.loading} error={statutes.error} onRetry={statutes.reload} />
      {statutes.data ? (
        <Card className="mt-5 p-5">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <StatuteControl value={statuteKey} statutes={statutes.data} onChange={setStatuteKey} />
            <label className="block w-full sm:max-w-[300px]">
              <span className="mb-1.5 block text-[11px] font-semibold text-muted-ink">Filter topics</span>
              <input className="h-10 w-full rounded-lg border border-[#d7c8b7] bg-paper px-3 text-xs outline-none focus:border-brass focus:ring-2 focus:ring-brass/15" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search title or key" />
            </label>
          </div>
          {filtered.length ? (
            <div className="mt-5 overflow-x-auto">
              <table className="w-full min-w-[720px] border-collapse text-left">
                <thead><tr className="border-b border-[#e7dbce] text-[10px] uppercase tracking-[0.1em] text-muted-ink"><th className="py-3 pr-4 font-semibold">Statute</th><th className="py-3 pr-4 font-semibold">Judgments</th><th className="py-3 pr-4 font-semibold">Verified propositions</th><th className="py-3 pr-4 font-semibold">Conflicts</th><th className="py-3 font-semibold">Actions</th></tr></thead>
                <tbody>
                  {filtered.map((statute) => (
                    <tr className="border-b border-[#f0e8df] last:border-0" key={statute.statute_key}>
                      <td className="py-4 pr-4"><p className="text-xs font-semibold text-espresso">{statute.display_name}</p><p className="mt-1 font-mono text-[9px] text-muted-ink">{statute.statute_key}</p></td>
                      <td className="py-4 pr-4 text-xs text-muted-ink">{formatNumber(statute.total_judgments)}</td>
                      <td className="py-4 pr-4 text-xs text-muted-ink">{formatNumber(statute.verified_propositions)}</td>
                      <td className="py-4 pr-4"><Badge tone="danger">{statute.conflict_count}</Badge><p className="mt-1 max-w-[210px] text-[10px] leading-4 text-muted-ink">{statute.sc_status_badge}</p></td>
                      <td className="py-4"><div className="flex flex-wrap gap-3"><Link to={`/radar?statute=${encodeURIComponent(statute.statute_key)}`} className="text-xs font-semibold text-oxblood hover:underline">Open radar</Link><Link to={`/investigation?statute=${encodeURIComponent(statute.statute_key)}`} className="text-xs font-semibold text-oxblood hover:underline">Investigate</Link></div></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <EmptyState title="No matching statutes" description="The backend returned no matching records." icon="search_off" />}
        </Card>
      ) : null}
    </>
  );
}

export function RadarPage() {
  const statutes = useApiResource("statutes", getStatutes);
  const [statuteKey, setStatuteKey] = useStatuteSelection(statutes.data ?? []);
  const graph = useApiResource(
    statuteKey,
    (signal) => getStatuteGraph(statuteKey, signal),
  );
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);
  const evidence = useApiResource(
    selectedNode?.id ?? "",
    (signal) => getEvidence(selectedNode!.id, signal),
  );
  const relationship = useApiResource(
    selectedEdge?.id ?? "",
    (signal) => getConflict(selectedEdge!.id, signal),
  );
  const selectedStatute = statutes.data?.find((item) => item.statute_key === statuteKey);

  useEffect(() => {
    setSelectedNode(null);
    setSelectedEdge(null);
  }, [statuteKey]);

  useEffect(() => {
    if (graph.data?.edges.length && !selectedEdge && !selectedNode) {
      setSelectedEdge(graph.data.edges[0]);
    }
  }, [graph.data, selectedEdge, selectedNode]);

  return (
    <>
      <PageHeader eyebrow="Workspace · network" title="Conflict radar" description="Explore court relationships and evidence from the selected backend corpus." actions={graph.data ? <FirstInvestigationLink statuteKey={statuteKey} graph={graph.data} children="Open investigation" /> : null} />
      <ApiState loading={statutes.loading} error={statutes.error} onRetry={statutes.reload} />
      {statutes.data ? <StatuteControl value={statuteKey} statutes={statutes.data} onChange={setStatuteKey} /> : null}
      <ApiState loading={graph.loading} error={graph.error} onRetry={graph.reload} />
      {graph.data ? (
        <Card className="mt-5 overflow-hidden p-0">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
            <div className="p-5 pb-0">
              <StatuteControl value={statuteKey} statutes={statutes.data ?? []} onChange={(value) => { setSelectedNode(null); setStatuteKey(value); }} />
            </div>
            <div className="flex flex-wrap gap-2 px-5 pb-1">
              <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-ink"><span className="h-2 w-2 rounded-full bg-[#b85b5c]" /> Conflict</span>
              <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-ink"><span className="h-2 w-2 rounded-full bg-[#5d9b78]" /> Agreement</span>
              <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-ink"><span className="h-2 w-2 rounded-full bg-[#c89d5d]" /> Distinguishable</span>
            </div>
          </div>
          <div className="grid gap-5 px-5 pb-5 xl:grid-cols-[minmax(0,1fr)_260px]">
            <div className="min-w-0">
              {graph.data.nodes.length ? (
                <ConflictGraphView
                  graph={graph.data}
                  onNodeSelect={(node) => {
                    setSelectedEdge(null);
                    setSelectedNode(node);
                  }}
                  onEdgeSelect={(edge) => {
                    setSelectedNode(null);
                    setSelectedEdge(edge);
                  }}
                />
              ) : <EmptyState title="No court propositions" description="The backend returned no verified proposition nodes for this statute." icon="account_balance" />}
              <p className="mt-2 flex items-center justify-between gap-3 text-[10px] text-muted-ink"><span>Each node is a verified proposition; P1, P2 and P3 distinguish propositions from the same court and date.</span><span className="hidden sm:inline">Supreme Court reference · court clusters · live relationships</span></p>
            </div>
            <aside className="rounded-xl border border-[#e8ded3] bg-[#fffaf4] p-4">
              {selectedEdge ? (
                <>
                  <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-brass">Selected relationship</p>
                  <h2 className="mt-1 font-editorial text-lg font-semibold text-espresso">{selectedEdge.label.replaceAll("_", " ")}</h2>
                  <div className="mt-4 space-y-3 text-xs">
                    <div className="flex justify-between gap-3"><span className="text-muted-ink">Confidence</span><strong className="text-espresso">{formatPercent(selectedEdge.confidence, 0)}</strong></div>
                    <div><span className="text-muted-ink">Reason</span><p className="mt-1 leading-5 text-espresso">{selectedEdge.reason}</p></div>
                    <div><span className="text-muted-ink">Supreme Court status</span><p className="mt-1 leading-5 text-espresso">{selectedEdge.sc_status}</p></div>
                  </div>
                  <ApiState loading={relationship.loading} error={relationship.error} onRetry={relationship.reload} />
                  {relationship.data ? (
                    <div className="mt-4 space-y-3 border-t border-[#e8ded3] pt-4">
                      <div>
                        <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-brass">How this label was reached</p>
                        <p className="mt-1 text-xs leading-5 text-espresso">
                          The system compared the same legal question and the two verified holdings below. The label describes the relationship between those holdings; it does not mean either court is generally right or wrong.
                        </p>
                      </div>
                      {[relationship.data.prop_a, relationship.data.prop_b].map((proposition, index) => (
                        <div className="rounded-lg border border-[#e8ded3] bg-[#f7f2eb] p-3" key={proposition.proposition_id}>
                          <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-muted-ink">
                            Holding {index === 0 ? "A" : "B"} · {proposition.court_name}
                          </p>
                          <p className="mt-1 text-xs font-semibold leading-5 text-espresso">{proposition.holding}</p>
                          <p className="mt-2 text-[11px] italic leading-4 text-muted-ink">“{proposition.quote}”</p>
                        </div>
                      ))}
                      {relationship.data.sc_prop ? (
                        <div className="rounded-lg border border-brass/30 bg-[#fbf4e7] p-3">
                          <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-brass">Supreme Court reference</p>
                          <p className="mt-1 text-xs leading-5 text-espresso">{relationship.data.sc_prop.holding}</p>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  <button type="button" className="mt-4 text-xs font-semibold text-oxblood hover:underline" onClick={() => setSelectedEdge(null)}>Clear selection</button>
                  <div className="my-5 border-t border-[#e8ded3]" />
                </>
              ) : null}
              <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-brass">Network summary</p>
              <h2 className="mt-1 font-editorial text-lg font-semibold text-espresso">{graph.data.display_name}</h2>
              <div className="mt-4 space-y-3">
                <div className="grid grid-cols-3 gap-2">
                  <div className="rounded-lg bg-[#f3e8d5] p-2"><strong className="block text-lg text-espresso">{new Set(graph.data.nodes.map((node) => node.court_id)).size}</strong><span className="text-[9px] uppercase tracking-[0.08em] text-muted-ink">Courts</span></div>
                  <div className="rounded-lg bg-[#f7e6e3] p-2"><strong className="block text-lg text-oxblood">{graph.data.edges.length}</strong><span className="text-[9px] uppercase tracking-[0.08em] text-muted-ink">Links</span></div>
                <div className="rounded-lg bg-[#e7f0e9] p-2"><strong className="block text-lg text-forest">{graph.data.nodes.filter((node) => node.level === "SC").length}</strong><span className="text-[9px] uppercase tracking-[0.08em] text-muted-ink">SC props</span></div>
                </div>
              </div>
              <div className="mt-4 border-t border-[#e8ded3] pt-4"><FirstInvestigationLink statuteKey={statuteKey} graph={graph.data} /></div>
              {selectedStatute ? <p className="mt-4 text-[10px] leading-4 text-muted-ink">{selectedStatute.sc_status_badge}</p> : null}
            </aside>
          </div>
          <div className="mx-5 mb-5 flex flex-wrap items-center justify-between gap-4 rounded-lg border border-[#e8ded3] bg-[#fffaf4] px-4 py-3">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-brass">Network legend</p>
              <p className="mt-1 text-[10px] text-muted-ink">Each node is an actual backend proposition. Pulses indicate live relationship traversal.</p>
            </div>
            <div className="flex flex-wrap gap-4 text-[10px] font-semibold text-muted-ink">
              <span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-full bg-[#526b72]" />Proposition</span>
              <span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-full bg-[#8f6c37]" />Supreme Court</span>
              <span><i className="mr-1 inline-block h-0.5 w-5 align-middle bg-[#a94c4d]" />Conflict</span>
              <span><i className="mr-1 inline-block h-0.5 w-5 align-middle bg-[#52896d]" />Agreement</span>
              <span><i className="mr-1 inline-block h-0.5 w-5 align-middle bg-[#c29a55]" />Distinguishable</span>
            </div>
          </div>
        </Card>
      ) : null}
      <EvidenceDrawer
        node={selectedNode}
        evidence={evidence.data}
        loading={evidence.loading}
        error={evidence.error}
        onClose={() => setSelectedNode(null)}
      />
    </>
  );
}

export function InvestigationPage() {
  const statutes = useApiResource("statutes", getStatutes);
  const [statuteKey, setStatuteKey] = useStatuteSelection(statutes.data ?? []);
  const [params] = useSearchParams();
  const requestedConflictId = params.get("conflict");
  const graph = useApiResource(
    requestedConflictId ? "" : statuteKey,
    (signal) => getStatuteGraph(statuteKey, signal),
  );
  const defaultConflict = graph.data?.edges.find((edge) => edge.label === "CONFLICT") ?? graph.data?.edges[0];
  const conflictId = requestedConflictId ?? defaultConflict?.id ?? "";
  const conflict = useApiResource(
    conflictId,
    (signal) => getConflict(conflictId, signal),
  );
  const statute = statutes.data?.find((item) => item.statute_key === statuteKey);

  return (
    <>
      <PageHeader eyebrow="Investigation · comparative view" title="Conflict investigation" description="Compare backend propositions, verified quotations, adjudication, and appellate status." actions={<LinkButton to={`/supreme-court?statute=${encodeURIComponent(statuteKey)}`}>Supreme Court status <ArrowRight size={14} /></LinkButton>} />
      <ApiState loading={statutes.loading} error={statutes.error} onRetry={statutes.reload} />
      {statutes.data ? <div className="mt-5"><StatuteControl value={statuteKey} statutes={statutes.data} onChange={setStatuteKey} /></div> : null}
      {!requestedConflictId ? <ApiState loading={graph.loading} error={graph.error} onRetry={graph.reload} empty={Boolean(graph.data && graph.data.edges.length === 0)} /> : null}
      <ApiState loading={conflict.loading} error={conflict.error} onRetry={conflict.reload} empty={!conflictId && Boolean(graph.data)} />
      {conflict.data ? (
        <>
          {conflict.data.statute_key !== statuteKey ? (
            <p className="mt-4 text-xs text-oxblood" role="alert">This conflict belongs to {conflict.data.statute_key}, not the selected statute.</p>
          ) : (
            <>
              <div className="mt-4"><Badge tone="danger">{conflict.data.label.replaceAll("_", " ")} · {conflict.data.conflict_id}</Badge></div>
              <div className="mt-5 grid gap-4 xl:grid-cols-2">
                {[conflict.data.prop_a, conflict.data.prop_b].map((proposition, index) => (
                  <PropositionCard proposition={proposition} label={index === 0 ? "Position A" : "Position B"} key={proposition.proposition_id} />
                ))}
              </div>
              <Card className="mt-5 p-5">
                <SectionTitle title="Backend adjudication" description="Label and panel output returned by the conflict endpoint." />
                <div className="grid gap-4 md:grid-cols-3">
                  <div><p className="text-[10px] uppercase tracking-[0.1em] text-muted-ink">Label</p><div className="mt-2"><Badge tone="danger">{conflict.data.label.replaceAll("_", " ")}</Badge></div></div>
                  <div><p className="text-[10px] uppercase tracking-[0.1em] text-muted-ink">Confidence</p><p className="mt-2 text-sm font-semibold text-espresso">{formatPercent(conflict.data.confidence, 0)}</p></div>
                  <div><p className="text-[10px] uppercase tracking-[0.1em] text-muted-ink">Panel votes</p><p className="mt-2 text-xs font-medium text-espresso">{conflict.data.votes.map((vote) => vote.replaceAll("_", " ")).join(" · ")}</p></div>
                </div>
                <p className="mt-4 rounded-lg bg-[#fbf4e7] p-3 text-xs leading-5 text-muted-ink">{conflict.data.reason}</p>
                {conflict.data.sc_prop ? <div className="mt-4"><PropositionCard proposition={conflict.data.sc_prop} label="Supreme Court" /></div> : null}
                <div className="mt-4 flex flex-wrap gap-2"><LinkButton to={`/evidence?statute=${encodeURIComponent(statuteKey)}`}>Open evidence explorer <ArrowRight size={14} /></LinkButton><LinkButton to={`/supreme-court?statute=${encodeURIComponent(statuteKey)}`}>Review SC status <ArrowRight size={14} /></LinkButton></div>
              </Card>
              {statute ? <Card className="mt-5 p-5"><SectionTitle title="Related statutory topic" /><p className="text-xs text-muted-ink">{statute.display_name}</p><Link to={`/radar?statute=${encodeURIComponent(statuteKey)}`} className="mt-3 inline-flex text-xs font-semibold text-oxblood hover:underline">Return to conflict radar →</Link></Card> : null}
            </>
          )}
        </>
      ) : null}
    </>
  );
}

function PropositionCard({ proposition, label }: { proposition: PropositionEvidence; label: string }) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div><p className="text-[10px] font-bold uppercase tracking-[0.12em] text-brass">{label}</p><h2 className="mt-1 font-editorial text-xl font-semibold text-espresso">{proposition.court_name}</h2></div>
        <Badge tone="success">{proposition.verify_status.replaceAll("_", " ")}</Badge>
      </div>
      <p className="mt-3 text-xs font-semibold text-espresso">{proposition.judgment_title}</p>
      <p className="mt-1 text-[10px] text-muted-ink">{proposition.cnr} · {proposition.decision_date}</p>
      <div className="mt-4"><SourceType uri={proposition.s3_uri} /></div>
      <div className="mt-4 rounded-lg border border-[#e8ded3] bg-[#fffaf4] p-4">
        <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-muted-ink">Holding</p>
        <p className="mt-2 text-xs leading-5 text-espresso">{proposition.holding}</p>
      </div>
      <blockquote className="mt-4 border-l-2 border-brass pl-3 font-editorial text-base leading-6 text-espresso">“{proposition.quote}”</blockquote>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-[#eee5db] pt-3">
        <span className="text-[10px] text-muted-ink">Verification score: {proposition.verify_score} · page {proposition.page}</span>
        <Link to={`/judgment/${encodeURIComponent(proposition.proposition_id)}`} className="text-xs font-semibold text-oxblood hover:underline">Inspect source →</Link>
      </div>
    </Card>
  );
}

export function EvidencePage() {
  const statutes = useApiResource("statutes", getStatutes);
  const [statuteKey, setStatuteKey] = useStatuteSelection(statutes.data ?? []);
  const [query, setQuery] = useState("");
  const graph = useApiResource(statuteKey, (signal) => getStatuteGraph(statuteKey, signal));
  const evidence = useApiResource(
    graph.data ? `${statuteKey}:${graph.data.nodes.map((node) => node.id).join(",")}` : "",
    async (signal) => {
      const nodes = graph.data?.nodes ?? [];
      return Promise.all(nodes.map((node) => getEvidence(node.id, signal)));
    },
  );
  const filtered = (evidence.data ?? []).filter((record) =>
    `${record.court_name} ${record.judgment_title} ${record.quote}`.toLowerCase().includes(query.toLowerCase()),
  );

  return (
    <>
      <PageHeader eyebrow="Investigation · provenance" title="Evidence explorer" description="Review verified proposition records and source documents retrieved from the backend." />
      <ApiState loading={statutes.loading} error={statutes.error} onRetry={statutes.reload} />
      {statutes.data ? <Card className="mt-5 p-5"><div className="flex flex-wrap items-end justify-between gap-4"><StatuteControl value={statuteKey} statutes={statutes.data} onChange={setStatuteKey} /><label className="block w-full sm:max-w-[320px]"><span className="mb-1.5 block text-[11px] font-semibold text-muted-ink">Search evidence</span><input className="h-10 w-full rounded-lg border border-[#d7c8b7] bg-paper px-3 text-xs outline-none focus:border-brass focus:ring-2 focus:ring-brass/15" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Court, title, or quotation" /></label></div></Card> : null}
      <ApiState loading={graph.loading || evidence.loading} error={graph.error ?? evidence.error} onRetry={graph.error ? graph.reload : evidence.reload} empty={Boolean(evidence.data && evidence.data.length === 0)} />
      <div className="mt-5 space-y-4">
        {filtered.map((record) => (
          <Card className="p-5" key={record.proposition_id}>
            <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-[10px] font-bold uppercase tracking-[0.12em] text-brass">{record.court_name}</p><h2 className="mt-1 font-editorial text-xl font-semibold text-espresso">{record.judgment_title}</h2><p className="mt-1 text-[10px] text-muted-ink">{record.cnr} · {record.decision_date}</p></div><Badge tone="success">{record.verify_status.replaceAll("_", " ")}</Badge></div>
            <div className="mt-3"><SourceType uri={record.s3_uri} /></div>
            <div className="mt-4 grid gap-4 md:grid-cols-[1fr_260px]">
              <div className="rounded-lg border border-[#e8ded3] bg-[#fffaf4] p-4"><p className="text-[10px] font-bold uppercase tracking-[0.1em] text-muted-ink">Verified quotation</p><blockquote className="mt-2 font-editorial text-base leading-6 text-espresso">“{record.quote}”</blockquote><p className="mt-3 text-xs leading-5 text-muted-ink">{record.holding}</p></div>
              <div className="space-y-3 rounded-lg bg-[#f7f2eb] p-4"><div><p className="text-[10px] text-muted-ink">Source page</p><p className="mt-1 text-xs font-semibold text-espresso">{record.page}</p></div><div><p className="text-[10px] text-muted-ink">Verification score</p><p className="mt-1 text-xs font-semibold text-espresso">{record.verify_score}</p></div><LinkButton to={`/judgment/${encodeURIComponent(record.proposition_id)}`} className="w-full">Open source viewer <ArrowRight size={14} /></LinkButton></div>
            </div>
          </Card>
        ))}
        {evidence.data && filtered.length === 0 ? <Card><EmptyState title="No matching evidence" description="Try another search term or switch the selected statutory topic." icon="search_off" /></Card> : null}
      </div>
    </>
  );
}

export function SupremeCourtPage() {
  const statutes = useApiResource("statutes", getStatutes);
  const [statuteKey, setStatuteKey] = useStatuteSelection(statutes.data ?? []);
  const graph = useApiResource(statuteKey, (signal) => getStatuteGraph(statuteKey, signal));
  const scNodes = graph.data?.nodes.filter((node) => node.level === "SC") ?? [];
  const conflictEdge = graph.data?.edges.find((edge) => edge.label === "CONFLICT");
  const conflict = useApiResource(
    conflictEdge?.id ?? "",
    (signal) => getConflict(conflictEdge!.id, signal),
  );

  return (
    <>
      <PageHeader eyebrow="Appellate treatment · status" title="Supreme Court status" description="Inspect Supreme Court propositions and linked appellate treatment returned by the backend." />
      <ApiState loading={statutes.loading} error={statutes.error} onRetry={statutes.reload} />
      {statutes.data ? <StatuteControl value={statuteKey} statutes={statutes.data} onChange={setStatuteKey} /> : null}
      <ApiState loading={graph.loading} error={graph.error} onRetry={graph.reload} />
      {graph.data ? (
        <Card className="mt-5 p-5">
          <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-[10px] font-bold uppercase tracking-[0.12em] text-brass">Selected topic</p><h2 className="mt-1 font-editorial text-2xl font-semibold text-espresso">{graph.data.display_name}</h2></div><Badge tone={scNodes.length ? "success" : "neutral"}>{scNodes.length ? "Supreme Court proposition found" : "No Supreme Court proposition in this corpus"}</Badge></div>
          <div className="mt-5 grid gap-4 md:grid-cols-3">
            <div className="rounded-lg bg-[#f7f2eb] p-4"><p className="text-[10px] text-muted-ink">SC judgments scanned</p><p className="mt-1 font-editorial text-2xl font-semibold text-espresso">{graph.data.sc_scanned_count}</p></div>
            <div className="rounded-lg bg-[#f7f2eb] p-4"><p className="text-[10px] text-muted-ink">SC propositions found</p><p className="mt-1 text-sm font-semibold text-espresso">{scNodes.length}</p></div>
            <div className="rounded-lg bg-[#f7f2eb] p-4"><p className="text-[10px] text-muted-ink">Conflict appellate status</p><p className="mt-1 text-sm font-semibold text-espresso">{conflict.data?.sc_status ?? "No conflict edge returned"}</p></div>
          </div>
          <ApiState loading={conflict.loading} error={conflict.error} onRetry={conflict.reload} />
          {scNodes.map((node) => <SupremeCourtNode node={node} key={node.id} />)}
          {!scNodes.length ? <p className="mt-5 text-xs leading-5 text-muted-ink">The selected backend corpus contains no verified Supreme Court proposition for this statute. This describes this corpus only; it is not a statement that no such authority exists.</p> : null}
          <LinkButton className="mt-4" to={`/investigation?statute=${encodeURIComponent(statuteKey)}${conflictEdge ? `&conflict=${encodeURIComponent(conflictEdge.id)}` : ""}`}>Return to investigation <ArrowRight size={14} /></LinkButton>
        </Card>
      ) : null}
    </>
  );
}

function SupremeCourtNode({ node }: { node: GraphNode }) {
  const evidence = useApiResource(node.id, (signal) => getEvidence(node.id, signal));
  return (
    <Card className="mt-5 p-4">
      <p className="text-xs font-semibold text-espresso">{node.court_name}</p>
      <p className="mt-1 text-xs leading-5 text-muted-ink">{node.holding_preview}</p>
      <ApiState loading={evidence.loading} error={evidence.error} onRetry={evidence.reload} />
      {evidence.data ? <div className="mt-3"><SourceType uri={evidence.data.s3_uri} /><p className="mt-3 text-xs text-espresso">{evidence.data.quote}</p><Link to={`/judgment/${encodeURIComponent(node.id)}`} className="mt-3 inline-flex text-xs font-semibold text-oxblood hover:underline">Open source →</Link></div> : null}
    </Card>
  );
}

export function IngestPage() {
  const courts = useApiResource("courts", getCourts);
  const [files, setFiles] = useState<File[]>([]);
  const [courtId, setCourtId] = useState("UPLOAD");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const firstCourt = courts.data?.[0];
    if (firstCourt && courtId === "UPLOAD") {
      setCourtId(firstCourt.id);
    }
  }, [courts.data, courtId]);

  function acceptFiles(nextFiles: File[]) {
    if (!nextFiles.length) return;
    const invalid = nextFiles.find((nextFile) =>
      !nextFile.name.toLowerCase().endsWith(".pdf") && nextFile.type !== "application/pdf"
    );
    if (invalid) {
      setFiles([]);
      setNotice("");
      setError(`Only PDF files are accepted: ${invalid.name}`);
      return;
    }
    setError(null);
    setFiles(nextFiles);
    setNotice(`${nextFiles.length} PDF${nextFiles.length === 1 ? "" : "s"} selected. Upload starts when you choose Upload and process.`);
  }

  async function submit() {
    if (!files.length || uploading) return;
    setError(null);
    setUploading(true);
    try {
      const { run_ids } = await uploadJudgments(files, courtId);
      navigate(`/processing?runs=${encodeURIComponent(run_ids.join(","))}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The PDF upload failed.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <>
      <PageHeader eyebrow="Operations · intake" title="Ingest judgments" description="Upload a PDF to the connected backend for extraction, verification, and conflict processing." />
      <div className="mt-5 grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
        <Card className="p-5">
          <SectionTitle title="Judgment PDFs" description="Select one or more PDFs. Each file gets its own persistent processing run." />
          <label className="mb-4 block max-w-xl">
            <span className="mb-1.5 block text-[11px] font-semibold text-muted-ink">Court attribution</span>
            <select
              className="h-10 w-full rounded-lg border border-[#d7c8b7] bg-paper px-3 text-xs text-espresso outline-none focus:border-brass focus:ring-2 focus:ring-brass/15"
              value={courtId}
              onChange={(event) => setCourtId(event.target.value)}
            >
              <option value="UPLOAD">Unverified court (not added to conflict radar)</option>
              {(courts.data ?? []).map((court) => (
                <option value={court.id} key={court.id}>{court.name}</option>
              ))}
            </select>
            <ApiState loading={courts.loading} error={courts.error} onRetry={courts.reload} />
          </label>
          <label className="flex min-h-[220px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-[#d8c6b0] bg-[#fffaf4] px-5 text-center transition-colors hover:border-brass hover:bg-[#fbf4e7]" onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); acceptFiles(Array.from(event.dataTransfer.files)); }}>
            <span className="grid h-12 w-12 place-items-center rounded-full bg-[#f4e8d5] text-brass"><Upload size={21} /></span>
            <span className="mt-3 text-sm font-semibold text-espresso">Drop a judgment PDF here</span>
            <span className="mt-1 text-xs text-muted-ink">or browse multiple files on this device</span>
            <input type="file" accept="application/pdf,.pdf" multiple className="sr-only" onChange={(event) => acceptFiles(Array.from(event.target.files ?? []))} />
          </label>
          {files.length ? <div className="mt-4 space-y-2">{files.map((file) => <div className="flex items-center justify-between gap-3 rounded-lg border border-[#e8ded3] bg-paper p-3" key={`${file.name}-${file.size}-${file.lastModified}`}><div className="flex min-w-0 items-center gap-2"><FileText size={17} className="shrink-0 text-brass" /><span className="truncate text-xs font-semibold text-espresso">{file.name}</span><span className="shrink-0 text-[10px] text-muted-ink">{(file.size / 1024 / 1024).toFixed(2)} MB</span></div></div>)}</div> : null}
          {notice ? <p className="mt-3 text-xs text-muted-ink" role="status">{notice}</p> : null}
          {error ? <p className="mt-3 text-xs text-oxblood" role="alert">{error}</p> : null}
          <Button className="mt-4" disabled={!files.length || uploading} onClick={() => void submit()}>{uploading ? `Uploading ${files.length} PDF${files.length === 1 ? "" : "s"}…` : `Upload and process ${files.length || ""}`} <ArrowRight size={15} /></Button>
        </Card>
        <Card className="p-5"><SectionTitle title="Processing details" /><ul className="space-y-3 text-xs leading-5 text-muted-ink">{["The selected PDF is sent to the configured backend.", "The backend returns a persistent run ID.", "Pipeline progress is read from the backend event stream."].map((item) => <li className="flex gap-2" key={item}><CheckCircle2 size={15} className="mt-0.5 shrink-0 text-forest" />{item}</li>)}</ul></Card>
      </div>
    </>
  );
}

export function ProcessingPage() {
  const [params] = useSearchParams();
  const runIds = (params.get("runs") ?? params.get("run") ?? "").split(",").filter(Boolean);
  const runId = runIds[0] ?? null;
  const run = useApiResource(runId ?? "", (signal) => getRun(runId!, signal));

  return (
    <>
      <PageHeader eyebrow="Operations · pipeline" title="Live processing" description="Current run status and events are read from the backend." actions={<LinkButton to="/runs">Run history</LinkButton>} />
      <ApiState loading={run.loading} error={run.error} onRetry={run.reload} empty={!runId} />
      {runIds.length > 1 ? <p className="mb-4 text-xs text-muted-ink">{runIds.length} files are processing independently. Each run is shown below.</p> : null}
      <div className="space-y-5">{runIds.map((id) => <LivePipelineMonitor runId={id} key={id} />)}</div>
    </>
  );
}

export function RunsPage() {
  const runs = useApiResource("runs", getRuns);
  return (
    <>
      <PageHeader eyebrow="Operations · audit trail" title="Run history" description="Persistent ingestion runs retrieved from the backend." actions={<LinkButton to="/ingest"><Upload size={14} /> Ingest judgment</LinkButton>} />
      <ApiState loading={runs.loading} error={runs.error} onRetry={runs.reload} empty={runs.data?.length === 0} />
      {runs.data?.length ? (
        <Card className="mt-5 overflow-hidden">
          <div className="overflow-x-auto p-5">
            <table className="w-full min-w-[780px] border-collapse text-left">
              <thead><tr className="border-b border-[#e7dbce] text-[10px] uppercase tracking-[0.1em] text-muted-ink"><th className="py-3 pr-4 font-semibold">Source</th><th className="py-3 pr-4 font-semibold">Run identifier</th><th className="py-3 pr-4 font-semibold">Kind</th><th className="py-3 pr-4 font-semibold">Started</th><th className="py-3 pr-4 font-semibold">State</th><th className="py-3 font-semibold">Details</th></tr></thead>
              <tbody>{runs.data.map((run) => <RunRow run={run} key={run.id} />)}</tbody>
            </table>
          </div>
        </Card>
      ) : null}
    </>
  );
}

function RunRow({ run }: { run: RunSummary }) {
  return (
    <tr className="border-b border-[#f0e8df] last:border-0">
      <td className="py-4 pr-4 text-xs text-espresso">{run.filename ?? "—"}</td>
      <td className="py-4 pr-4 font-mono text-[10px] text-espresso">{run.id}</td>
      <td className="py-4 pr-4 text-xs text-muted-ink">{run.kind}</td>
      <td className="py-4 pr-4 text-xs text-muted-ink">{new Date(run.started_at).toLocaleString()}</td>
      <td className="py-4 pr-4"><Badge tone={run.status === "failed" ? "danger" : run.status === "running" ? "brass" : "success"}>{run.status}</Badge></td>
      <td className="py-4"><Link className="text-xs font-semibold text-oxblood hover:underline" to={`/processing?run=${encodeURIComponent(run.id)}`}>Open events →</Link></td>
    </tr>
  );
}

export function EvaluationPage() {
  const evaluation = useApiResource("evaluation", getEvaluation);
  const metrics = evaluation.data;
  const metricBars = metrics ? [
    ["Precision", metrics.precision],
    ["Recall", metrics.recall],
    ["F1 score", metrics.f1_score],
    ["Cohen's kappa", metrics.cohens_kappa],
  ] as const : [];
  const matrix = metrics ? [
    ["Actual conflict", metrics.confusion_matrix.TP, metrics.confusion_matrix.FN],
    ["Actual agreement", metrics.confusion_matrix.FP, metrics.confusion_matrix.TN],
  ] as const : [];

  return (
    <>
      <PageHeader eyebrow="Intelligence · evaluation" title="Evaluation & metrics" description="Metrics calculated by the backend against the test split and stored propositions." />
      <ApiState loading={evaluation.loading} error={evaluation.error} onRetry={evaluation.reload} />
      {metrics ? (
        <>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{metricBars.map(([name, value]) => <MetricCard key={name} label={name} value={formatPercent(value, 0)} note="Backend evaluation" icon="query_stats" tone={name === "F1 score" ? "green" : "brass"} />)}</div>
          <div className="mt-5 grid gap-5 xl:grid-cols-2">
            <Card className="p-5"><SectionTitle title="Metric profile" description={`${metrics.total_gold_pairs_test} gold pairs in test split`} />{metricBars.map(([name, value]) => <div className="mb-4 last:mb-0" key={name}><div className="mb-1.5 flex justify-between text-xs"><span className="font-medium text-espresso">{name}</span><span className="text-muted-ink">{formatPercent(value, 0)}</span></div><div className="h-2 overflow-hidden rounded-full bg-[#efe6dc]"><div className="h-full rounded-full bg-brass" style={{ width: `${Math.min(100, Math.max(0, value * 100))}%` }} /></div></div>)}<p className="mt-4 text-[10px] leading-4 text-muted-ink">Baseline F1: {formatPercent(metrics.baseline_f1_score, 0)} · change: {formatPercent(metrics.f1_improvement_over_baseline, 1)}</p></Card>
            <Card className="p-5"><SectionTitle title="Confusion matrix" description="Backend test-split counts." /><div className="overflow-x-auto"><table className="w-full border-collapse text-center text-xs"><thead><tr className="text-[10px] text-muted-ink"><th className="p-3 text-left">Actual / predicted</th><th className="p-3">Conflict</th><th className="p-3">Not conflict</th></tr></thead><tbody>{matrix.map(([label, positive, negative]) => <tr className="border-t border-[#e9dfd3]" key={label}><th className="p-3 text-left text-[11px] font-semibold text-espresso">{label}</th><td className="p-3"><span className="inline-flex min-w-16 justify-center rounded bg-[#edf4ed] px-3 py-2 font-semibold text-forest">{positive}</span></td><td className="p-3"><span className="inline-flex min-w-16 justify-center rounded bg-[#fbefec] px-3 py-2 font-semibold text-oxblood">{negative}</span></td></tr>)}</tbody></table></div><p className="mt-4 text-xs leading-5 text-muted-ink">{metrics.conflict_definition}</p></Card>
          </div>
          <Card className="mt-5 p-5"><SectionTitle title="Extraction verification" description="Counts from proposition records in the backend database." /><div className="grid gap-4 sm:grid-cols-3"><div><p className="text-[10px] text-muted-ink">Attempts</p><p className="mt-1 text-lg font-semibold text-espresso">{formatNumber(metrics.total_extractions_attempted)}</p></div><div><p className="text-[10px] text-muted-ink">Dropped</p><p className="mt-1 text-lg font-semibold text-oxblood">{formatNumber(metrics.total_extractions_dropped)}</p></div><div><p className="text-[10px] text-muted-ink">Drop rate</p><p className="mt-1 text-lg font-semibold text-espresso">{formatPercent(metrics.hallucination_drop_rate, 1)}</p></div></div></Card>
        </>
      ) : null}
    </>
  );
}

export function BriefsPage() {
  const statutes = useApiResource("statutes", getStatutes);
  const [statuteKey, setStatuteKey] = useStatuteSelection(statutes.data ?? []);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const statute = statutes.data?.find((item) => item.statute_key === statuteKey);

  async function downloadBrief() {
    if (!statuteKey || downloading) return;
    setDownloading(true);
    setError(null);
    try {
      const blob = await getBrief(statuteKey);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${statuteKey}-forum-risk-brief.pdf`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The brief could not be generated.");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <>
      <PageHeader eyebrow="Reports · research brief" title="Forum-risk briefs" description="Generate and download a PDF brief using the backend corpus." />
      <ApiState loading={statutes.loading} error={statutes.error} onRetry={statutes.reload} />
      {statutes.data ? (
        <div className="mt-5 grid gap-5 xl:grid-cols-[350px_minmax(0,1fr)]">
          <Card className="h-fit p-5"><SectionTitle title="Brief parameters" description="Select the statutory topic for the backend-generated report." /><StatuteControl value={statuteKey} statutes={statutes.data} onChange={setStatuteKey} /><Button className="mt-4 w-full" disabled={!statuteKey || downloading} onClick={() => void downloadBrief()}><ArrowDownToLine size={14} />{downloading ? "Generating PDF…" : "Generate and download PDF"}</Button>{error ? <p className="mt-3 text-xs text-oxblood" role="alert">{error}</p> : null}</Card>
          <Card className="min-h-[350px] p-5">{statute ? <><div className="flex flex-wrap items-start justify-between gap-3 border-b border-[#e8ded3] pb-4"><div><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-brass">Backend-generated brief</p><h2 className="mt-1 font-editorial text-2xl font-semibold text-espresso">{statute.display_name}</h2></div><Badge tone="neutral">Research support · not legal advice</Badge></div><div className="mt-4 space-y-4 text-xs leading-6 text-muted-ink"><p><strong className="text-espresso">Corpus counts.</strong> {formatNumber(statute.total_judgments)} judgments and {formatNumber(statute.verified_propositions)} verified propositions.</p><p><strong className="text-espresso">Conflict signals.</strong> {statute.conflict_count} records from the current backend database.</p><p><strong className="text-espresso">Appellate status.</strong> {statute.sc_status_badge}</p><p className="rounded-lg bg-[#fbf4e7] p-3">Review the source judgments and confirm current law before relying on this report.</p></div></> : <EmptyState title="No statute selected" description="The backend has no statutory topics available." icon="description" />}</Card>
        </div>
      ) : null}
    </>
  );
}

export function SystemHealthPage() {
  const health = useApiResource("health", getHealth);
  return (
    <>
      <PageHeader eyebrow="System · connectivity" title="System health" description="Connection and corpus status reported by the backend health endpoint." />
      <ApiState loading={health.loading} error={health.error} onRetry={health.reload} />
      {health.data ? (
        <>
          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <Card className="p-5"><div className="flex items-start justify-between gap-3"><div><p className="text-[10px] uppercase tracking-[0.12em] text-muted-ink">API service</p><h2 className="mt-1 font-editorial text-2xl font-semibold text-espresso">{health.data.status}</h2></div><Badge tone="success">Connected</Badge></div><p className="mt-3 text-xs leading-5 text-muted-ink">Model provider: {health.data.llm_provider}</p><p className="mt-1 text-xs text-muted-ink">Frontend API base: /api</p></Card>
            <Card className="p-5"><div className="flex items-start justify-between gap-3"><div><p className="text-[10px] uppercase tracking-[0.12em] text-muted-ink">Data source</p><h2 className="mt-1 font-editorial text-2xl font-semibold text-espresso">AWS S3 DATA</h2></div><Badge tone="neutral">AWS S3 DATA</Badge></div><p className="mt-3 text-xs leading-5 text-muted-ink">Judgments and conflict relationships are retrieved from the connected data source.</p></Card>
          </div>
          <Card className="mt-5 p-5">
            <SectionTitle
              title="REST API documentation"
              description="Interactive documentation generated directly from the FastAPI backend."
            />
            <div className="mt-4 flex flex-wrap gap-3">
              <a
                className="inline-flex min-h-10 items-center rounded-lg bg-oxblood px-4 text-xs font-semibold text-white hover:bg-oxblood/90"
                href="/docs"
                target="_blank"
                rel="noreferrer"
              >
                Open Swagger UI
              </a>
              <a
                className="inline-flex min-h-10 items-center rounded-lg border border-[#d7c8b7] px-4 text-xs font-semibold text-espresso hover:border-brass"
                href="/redoc"
                target="_blank"
                rel="noreferrer"
              >
                Open ReDoc
              </a>
              <a
                className="inline-flex min-h-10 items-center rounded-lg border border-[#d7c8b7] px-4 text-xs font-semibold text-espresso hover:border-brass"
                href="/openapi.json"
                target="_blank"
                rel="noreferrer"
              >
                View OpenAPI JSON
              </a>
            </div>
            <div className="mt-5 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {["GET /api/health", "GET /api/statutes", "GET /api/statutes/{key}/graph", "GET /api/conflicts/{id}", "GET /api/evidence/{id}", "GET /api/evidence/{id}/page.png", "POST /api/ingest", "GET /api/runs", "GET /api/runs/{id}", "GET /api/runs/{id}/events", "GET /api/eval/summary", "GET /api/briefs/{key}.pdf"].map((endpoint) => <code className="rounded bg-[#f7f2eb] px-3 py-2 font-mono text-[10px] text-muted-ink" key={endpoint}>{endpoint}</code>)}
            </div>
          </Card>
        </>
      ) : null}
    </>
  );
}

export function JudgmentPage() {
  const { propositionId = "" } = useParams();
  const evidence = useApiResource(
    propositionId,
    (signal) => getEvidence(propositionId, signal),
  );
  const image = evidence.data ? evidencePageUrl(evidence.data) : "";

  return (
    <>
      <PageHeader eyebrow="Source · judgment" title="Judgment viewer" description="Verified proposition and source page retrieved from the backend." actions={<LinkButton to="/evidence">Back to evidence</LinkButton>} />
      <ApiState loading={evidence.loading} error={evidence.error} onRetry={evidence.reload} />
      {evidence.data ? (
        <div className="mt-5 grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
          <Card className="h-fit p-5">
            <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-[10px] font-bold uppercase tracking-[0.12em] text-brass">{evidence.data.court_name}</p><h2 className="mt-1 font-editorial text-2xl font-semibold text-espresso">{evidence.data.judgment_title}</h2></div><Badge tone="success">{evidence.data.verify_status.replaceAll("_", " ")}</Badge></div>
            <p className="mt-3 text-xs text-muted-ink">{evidence.data.cnr} · {evidence.data.decision_date}</p>
            <div className="mt-4"><SourceType uri={evidence.data.s3_uri} /></div>
            <h3 className="mt-5 text-[10px] font-bold uppercase tracking-[0.12em] text-muted-ink">Legal question</h3><p className="mt-2 text-sm leading-6 text-espresso">{evidence.data.question}</p>
            <h3 className="mt-5 text-[10px] font-bold uppercase tracking-[0.12em] text-muted-ink">Holding</h3><p className="mt-2 text-sm leading-6 text-espresso">{evidence.data.holding}</p>
            <blockquote className="mt-5 border-l-2 border-brass pl-3 font-editorial text-base leading-6 text-espresso">“{evidence.data.quote}”</blockquote>
            <p className="mt-3 text-[10px] text-muted-ink">Page {evidence.data.page} · characters {evidence.data.char_start}–{evidence.data.char_end} · verification score {evidence.data.verify_score}</p>
          </Card>
          <Card className="p-4"><SectionTitle title="Source PDF page" description={`Page ${evidence.data.page} with the verified quote locator.`} /><img className="mt-4 h-auto w-full border border-[#e5d8c8] bg-white" src={image} alt={`Source judgment page ${evidence.data.page}`} /></Card>
        </div>
      ) : null}
    </>
  );
}

export function NotFoundPage() {
  return (
    <Card className="p-8 text-center">
      <h1 className="font-editorial text-3xl font-semibold text-espresso">Page not found</h1>
      <p className="mt-2 text-sm text-muted-ink">That workspace route does not exist.</p>
      <LinkButton className="mt-5" to="/overview">Return to overview</LinkButton>
    </Card>
  );
}
