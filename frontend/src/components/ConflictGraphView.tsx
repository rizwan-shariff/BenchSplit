import type {
  Core,
  EdgeDefinition,
  ElementDefinition,
  NodeDefinition,
} from "cytoscape";
import { Maximize2, Minus, Plus, Scan } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { GraphEdge, GraphNode, StatuteGraphResponse } from "../types/api";

interface ConflictGraphViewProps {
  graph: StatuteGraphResponse;
  onNodeSelect: (node: GraphNode) => void;
  onEdgeSelect: (edge: GraphEdge) => void;
}

export default function ConflictGraphView({
  graph,
  onNodeSelect,
  onEdgeSelect,
}: ConflictGraphViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<Core>();
  const onNodeSelectRef = useRef(onNodeSelect);
  const onEdgeSelectRef = useRef(onEdgeSelect);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    onNodeSelectRef.current = onNodeSelect;
    onEdgeSelectRef.current = onEdgeSelect;
  }, [onEdgeSelect, onNodeSelect]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    let disposed = false;
    let pulseTimer: number | undefined;
    setLoadError(null);

    void import("cytoscape")
      .then(({ default: cytoscape }) => {
        if (disposed) return;
        const nodeById = new Map(graph.nodes.map((node) => [node.id, node]));
        const edgeById = new Map(graph.edges.map((edge) => [edge.id, edge]));
        const nodesByCourt = new Map<string, GraphNode[]>();
        graph.nodes.forEach((node) => {
          const courtNodes = nodesByCourt.get(node.court_id) ?? [];
          courtNodes.push(node);
          nodesByCourt.set(node.court_id, courtNodes);
        });
        const supremeNodes = [...graph.nodes.filter((node) => node.level === "SC")];
        const highCourtGroups = [...nodesByCourt.entries()]
          .filter(([, nodes]) => nodes[0]?.level !== "SC")
          .sort(([left], [right]) => left.localeCompare(right));
        const courtCenter = { x: 445, y: 270 };
        const nodeElements: NodeDefinition[] = [];
        const clusterElements: NodeDefinition[] = [];
        const relationshipByNode = new Map<string, Set<GraphEdge["label"]>>();
        graph.edges.forEach((edge) => {
          [edge.source, edge.target].forEach((nodeId) => {
            const labels = relationshipByNode.get(nodeId) ?? new Set<GraphEdge["label"]>();
            labels.add(edge.label);
            relationshipByNode.set(nodeId, labels);
          });
        });
        const nodeClass = (node: GraphNode) => {
          const labels = relationshipByNode.get(node.id) ?? new Set();
          if (labels.has("CONFLICT")) return "conflict-bubble";
          if (labels.has("AGREE")) return "agree-bubble";
          if (labels.has("DISTINGUISHABLE_ON_FACTS")) return "distinguishable-bubble";
          return "neutral-bubble";
        };
        const addCourtNodes = (nodes: GraphNode[], centerX: number, centerY: number, isSupreme: boolean) => {
          const courtId = nodes[0]?.court_id;
          if (!courtId) return;
          clusterElements.push({
            group: "nodes",
            data: {
              id: `cluster-${courtId}`,
              label: nodes[0].court_short,
            },
            position: { x: centerX, y: centerY },
            classes: isSupreme ? "court-cluster supreme-cluster" : "court-cluster",
          });
          nodes.forEach((node, index) => {
            const isFocal = isSupreme && index === 0;
            const angle = (index / Math.max(nodes.length, 1)) * Math.PI * 2 - Math.PI / 2;
            const radius = isFocal ? 0 : isSupreme ? 74 : Math.min(78, 28 + nodes.length * 8);
            nodeElements.push({
              group: "nodes",
              data: {
                id: node.id,
                label: `${node.court_short}\n${isSupreme ? "SC" : "P"}${index + 1}`,
                court: node.court_name,
                detail: `${node.judgment_title} · ${node.decision_date}`,
              },
              position: {
                x: centerX + Math.cos(angle) * radius,
                y: centerY + Math.sin(angle) * radius,
              },
              classes: [
                isFocal ? "supreme-focal" : isSupreme ? "supreme" : "proposition",
                nodeClass(node),
              ].filter(Boolean).join(" "),
            });
          });
        };
        addCourtNodes(supremeNodes, courtCenter.x, courtCenter.y, true);
        highCourtGroups.forEach(([, nodes], groupIndex) => {
          const angle = (groupIndex / Math.max(highCourtGroups.length, 1)) * Math.PI * 2 - Math.PI / 2;
          addCourtNodes(
            nodes,
            courtCenter.x + Math.cos(angle) * 350,
            courtCenter.y + Math.sin(angle) * 220,
            false,
          );
        });
        const edgeElements: EdgeDefinition[] = graph.edges.map((edge) => ({
          group: "edges",
          data: {
            id: edge.id,
            source: edge.source,
            target: edge.target,
            label: edge.label.replaceAll("_", " "),
            confidence: `${Math.round(edge.confidence * 100)}%`,
          },
          classes: edge.label.toLowerCase(),
        }));
        const elements: ElementDefinition[] = [...clusterElements, ...nodeElements, ...edgeElements];
        const instance = cytoscape({
          container,
          elements,
          style: [
            {
              selector: "node",
              style: {
                shape: "ellipse",
                "background-color": "#526b72",
                "border-color": "#d7b26a",
                "border-width": "1px",
                color: "#fff8f3",
                label: "data(label)",
                "font-family": "Inter, sans-serif",
                "font-size": "9px",
                "font-weight": 600,
                "text-wrap": "wrap",
                "text-max-width": "80px",
                "text-valign": "center",
                "text-halign": "center",
                width: "54px",
                height: "54px",
                "overlay-opacity": 0,
              },
            },
            {
              selector: "node.court-cluster",
              style: {
                shape: "ellipse",
                "background-color": "#dfe8ea",
                "background-opacity": 0.62,
                "border-color": "#b9c9cc",
                "border-style": "dashed",
                "border-width": "1px",
                color: "#526b72",
                label: "data(label)",
                "font-size": "10px",
                "font-weight": 700,
                "text-valign": "top",
                "text-margin-y": -8,
                width: "210px",
                height: "210px",
                "z-index": 0,
                events: "no",
              },
            },
            {
              selector: "node.supreme-cluster",
              style: {
                shape: "ellipse",
                "background-color": "#f2e7cf",
                "background-opacity": 0.7,
                "border-color": "#c29a55",
                color: "#765324",
                width: "210px",
                height: "210px",
                "z-index": 0,
                events: "no",
              },
            },
            {
              selector: "node.conflict-bubble",
              style: {
                "background-color": "#a94c4d",
                "border-color": "#7f3538",
              },
            },
            {
              selector: "node.agree-bubble",
              style: {
                "background-color": "#52896d",
                "border-color": "#37684f",
              },
            },
            {
              selector: "node.distinguishable-bubble",
              style: {
                "background-color": "#c29a55",
                "border-color": "#916f37",
              },
            },
            {
              selector: "node.neutral-bubble",
              style: {
                "background-color": "#526b72",
                "border-color": "#849ca0",
              },
            },
            {
              selector: "node.supreme",
              style: {
                "background-color": "#8f6c37",
                "border-color": "#f0ce84",
                "border-width": "2px",
                width: "62px",
                height: "62px",
              },
            },
            {
              selector: "node.supreme-focal",
              style: {
                "background-color": "#765324",
                "border-color": "#ffe0a0",
                "border-width": "4px",
                "font-size": "11px",
                width: "92px",
                height: "92px",
              },
            },
            {
              selector: "edge",
              style: {
                width: "1px",
                "line-color": "#91a4a8",
                "target-arrow-shape": "none",
                "curve-style": "bezier",
                "line-style": "solid",
                "line-cap": "round",
                "line-opacity": 0.58,
              },
            },
            {
              selector: "edge.conflict",
              style: {
                "line-color": "#b86b6c",
                "line-opacity": 0.58,
              },
            },
            {
              selector: "edge.agree",
              style: {
                "line-color": "#709b82",
                "line-opacity": 0.58,
              },
            },
            {
              selector: "edge.distinguishable_on_facts",
              style: {
                "line-color": "#c6a66f",
                "line-opacity": 0.58,
              },
            },
            {
              selector: "edge.connected",
              style: {
                width: "3px",
                "line-opacity": 1,
              },
            },
            {
              selector: "edge.pulse",
              style: {
                width: "2px",
                "line-opacity": 0.95,
              },
            },
            {
              selector: "edge.conflict.pulse",
              style: {
                "line-color": "#b85b5c",
              },
            },
            {
              selector: "edge.agree.pulse",
              style: {
                "line-color": "#5d9b78",
              },
            },
            {
              selector: "edge.distinguishable_on_facts.pulse",
              style: {
                "line-color": "#c89d5d",
              },
            },
            {
              selector: ":selected",
              style: {
                "border-color": "#fff4d6",
                "border-width": "3px",
              },
            },
          ],
          layout: { name: "preset", fit: true, padding: 55 },
          minZoom: 0.35,
          maxZoom: 2,
          userZoomingEnabled: true,
          userPanningEnabled: true,
        });
        instanceRef.current = instance;
        let pulseIndex = 0;
        const pulseEdges = graph.edges;
        if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches && pulseEdges.length) {
          pulseTimer = window.setInterval(() => {
            instance.edges().removeClass("pulse");
            const edge = pulseEdges[pulseIndex % pulseEdges.length];
            instance.getElementById(edge.id).addClass("pulse");
            pulseIndex += 1;
          }, 1400);
        }
        instance.on("tap", "node", (event) => {
          const node = nodeById.get(event.target.id());
          if (!node) return;
          instance.elements().removeClass("connected");
          event.target.connectedEdges().addClass("connected");
          onNodeSelectRef.current(node);
        });
        instance.on("tap", "edge", (event) => {
          const edge = edgeById.get(event.target.id());
          if (!edge) return;
          instance.elements().removeClass("connected");
          event.target.addClass("connected");
          onEdgeSelectRef.current(edge);
        });
        instance.on("mouseover", "node", (event) => event.target.addClass("connected"));
        instance.on("mouseout", "node", (event) => event.target.removeClass("connected"));
      })
      .catch((error: unknown) => {
        if (!disposed) {
          setLoadError(error instanceof Error ? `Unable to load the graph: ${error.message}` : "Unable to load the graph.");
        }
      });

    return () => {
      disposed = true;
      if (pulseTimer) window.clearInterval(pulseTimer);
      instanceRef.current?.destroy();
      instanceRef.current = undefined;
    };
  }, [graph]);

  const zoom = (amount: number) => {
    const instance = instanceRef.current;
    if (!instance) return;
    instance.zoom({ level: instance.zoom() + amount, renderedPosition: { x: instance.width() / 2, y: instance.height() / 2 } });
  };

  return (
    <div className="relative">
      <div ref={containerRef} className="h-[430px] w-full rounded-xl border border-[#cfdae0] bg-[#eaf0f3] shadow-inner sm:h-[540px]" role="img" aria-label="Interactive judicial proposition relationship graph" aria-busy={!loadError} />
      <div className="pointer-events-none absolute left-1/2 top-3 -translate-x-1/2 rounded-full border border-[#d6b36d] bg-[#fff9ed]/90 px-3 py-1 text-[9px] font-bold uppercase tracking-[0.12em] text-[#765324] shadow-sm">
        Supreme Court · central reference
      </div>
      <div className="absolute left-3 top-3 flex flex-col overflow-hidden rounded-lg border border-[#c7d2d7] bg-[#f7fafb]/90 shadow-sm">
        <button type="button" className="grid h-9 w-9 place-items-center text-[#526b72] hover:bg-white" onClick={() => zoom(0.15)} aria-label="Zoom in"><Plus size={15} /></button>
        <button type="button" className="grid h-9 w-9 place-items-center border-t border-[#d6e0e3] text-[#526b72] hover:bg-white" onClick={() => zoom(-0.15)} aria-label="Zoom out"><Minus size={15} /></button>
        <button type="button" className="grid h-9 w-9 place-items-center border-t border-[#d6e0e3] text-[#526b72] hover:bg-white" onClick={() => instanceRef.current?.fit(undefined, 55)} aria-label="Fit graph"><Scan size={15} /></button>
        <button type="button" className="grid h-9 w-9 place-items-center border-t border-[#d6e0e3] text-[#526b72] hover:bg-white" onClick={() => instanceRef.current?.center()} aria-label="Center graph"><Maximize2 size={14} /></button>
      </div>
      {loadError ? <p className="absolute inset-x-4 top-4 rounded-lg border border-[#e3c2bc] bg-[#fff7f4] p-3 text-xs text-oxblood" role="alert">{loadError}</p> : null}
    </div>
  );
}
