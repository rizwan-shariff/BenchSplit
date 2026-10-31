import { ChevronDown } from "lucide-react";
import { cn } from "../lib/utils";
import type { StatuteSummary } from "../types/api";

interface StatuteSelectorProps {
  value: string;
  statutes: StatuteSummary[];
  onChange: (value: string) => void;
  className?: string;
  label?: string;
}

export default function StatuteSelector({
  value,
  statutes,
  onChange,
  className,
  label = "Select statute",
}: StatuteSelectorProps) {
  return (
    <label className={cn("block", className)}>
      <span className="mb-1.5 block text-[11px] font-semibold text-muted-ink">{label}</span>
      <span className="relative block">
        <select
          className="h-10 w-full appearance-none rounded-lg border border-[#d7c8b7] bg-paper pl-3 pr-9 text-xs font-medium text-espresso outline-none focus:border-brass focus:ring-2 focus:ring-brass/15"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          disabled={statutes.length === 0}
        >
          {statutes.length === 0 ? <option value="">No statutes available</option> : null}
          {statutes.map((statute) => (
            <option key={statute.statute_key} value={statute.statute_key}>
              {statute.display_name}
            </option>
          ))}
        </select>
        <ChevronDown
          className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-muted-ink"
          size={15}
          aria-hidden="true"
        />
      </span>
    </label>
  );
}
