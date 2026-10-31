import { Activity, Search } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { screens } from "../data/screens";
import { getHealth, getStatutes } from "../services/api";
import { useApiResource } from "../hooks/useApiResource";
import type { StatuteSummary } from "../types/api";

interface TopbarProps {
  title: string;
}

export default function Topbar({ title }: TopbarProps) {
  const [query, setQuery] = useState("");
  const navigate = useNavigate();
  const health = useApiResource("health", getHealth);
  const statutes = useApiResource<StatuteSummary[]>("statutes", getStatutes);
  const datasetLabel =
    health.data?.dataset_mode === "synthetic-test"
      ? "AWS S3 DATA"
      : health.data?.dataset_mode === "mixed"
        ? "AWS S3 DATA"
        : health.data?.dataset_mode === "empty"
          ? "AWS S3 DATA"
          : health.data?.dataset_mode === "ingested"
            ? "AWS S3 DATA"
            : health.loading
              ? "Connecting"
              : "Backend offline";

  function submitSearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = query.trim().toLowerCase();
    if (!value) return;

    const statute = statutes.data?.find(
      (item) =>
        item.display_name.toLowerCase().includes(value) ||
        item.statute_key.toLowerCase().includes(value),
    );
    if (statute) {
      navigate(`/statutes?key=${encodeURIComponent(statute.statute_key)}`);
      setQuery("");
      return;
    }

    const screen = screens.find((item) => item.title.toLowerCase().includes(value));
    if (screen) {
      navigate(screen.path);
      setQuery("");
    }
  }

  return (
    <header className="sticky top-0 z-20 flex h-[68px] items-center justify-between gap-6 border-b border-[#e5d8c8] bg-paper/95 px-8 backdrop-blur">
      <div className="flex min-w-0 items-center gap-3">
        <div className="min-w-0">
          <p className="truncate text-[10px] font-semibold uppercase tracking-[0.13em] text-muted-ink">
            Judicial workspace
          </p>
          <p className="truncate text-sm font-semibold text-espresso">{title}</p>
        </div>
      </div>

      <form className="relative w-full max-w-[390px]" onSubmit={submitSearch} role="search">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#94887d]"
          size={16}
        />
        <input
          className="h-10 w-full rounded-lg border border-[#e3d8ca] bg-[#faf6ef] pl-9 pr-3 text-xs text-espresso outline-none placeholder:text-[#9b9086] focus:border-brass focus:ring-2 focus:ring-brass/15"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search statutes or workspace pages"
          aria-label="Search statutes or workspace pages"
        />
      </form>

      <div className="flex shrink-0 items-center gap-2 sm:gap-3">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-[#e2cfad] bg-[#fbf4e7] px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-[0.08em] text-[#76592a]">
          <span className={`h-1.5 w-1.5 rounded-full ${health.data?.status === "ok" ? "bg-forest" : "bg-oxblood"}`} />
          {datasetLabel}
        </span>
        <button
          type="button"
          className="inline-flex min-h-9 items-center gap-2 rounded-lg border border-[#d7c8b7] bg-paper px-3 text-xs font-semibold text-espresso hover:border-brass"
          onClick={() => navigate("/system-health")}
          aria-label="Open backend connection status"
        >
          <Activity size={15} />
          {health.data?.llm_provider ?? "Service status"}
        </button>
      </div>
    </header>
  );
}
