export const screens = [
  { path: "/overview", title: "Overview" },
  { path: "/statutes", title: "Statute Explorer" },
  { path: "/radar", title: "Conflict Radar" },
  { path: "/investigation", title: "Conflict Investigation" },
  { path: "/evidence", title: "Evidence Explorer" },
  { path: "/supreme-court", title: "Supreme Court status" },
  { path: "/ingest", title: "Ingest judgments" },
  { path: "/processing", title: "Live processing" },
  { path: "/runs", title: "Run history" },
  { path: "/evaluation", title: "Evaluation & metrics" },
  { path: "/briefs", title: "Forum-risk briefs" },
  { path: "/system-health", title: "System health" },
] as const;

export const screenByPath = new Map<string, (typeof screens)[number]>(
  screens.map((screen) => [screen.path, screen]),
);
