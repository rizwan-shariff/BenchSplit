import {
  Activity,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  FileCheck2,
  FileSearch,
  Gauge,
  Gavel,
  History,
  LayoutDashboard,
  LogOut,
  Network,
  Scale,
  ScrollText,
  Sparkles,
  Upload,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import { cn } from "../lib/utils";

const groups = [
  {
    label: "Workspace",
    number: "01",
    links: [
      { to: "/overview", label: "Overview", icon: LayoutDashboard },
      { to: "/radar", label: "Conflict Radar", icon: Network },
      { to: "/statutes", label: "Statute Explorer", icon: BookOpen },
    ],
  },
  {
    label: "Investigation",
    number: "02",
    links: [
      { to: "/investigation", label: "Conflict Investigation", icon: Scale },
      { to: "/evidence", label: "Evidence Explorer", icon: FileSearch },
      { to: "/supreme-court", label: "Supreme Court status", icon: Gavel },
    ],
  },
  {
    label: "Operations",
    number: "03",
    links: [
      { to: "/ingest", label: "Ingest judgments", icon: Upload },
      { to: "/processing", label: "Live processing", icon: Activity },
      { to: "/runs", label: "Run history", icon: History },
    ],
  },
  {
    label: "Reports",
    number: "04",
    links: [
      { to: "/evaluation", label: "Evaluation & metrics", icon: Gauge },
      { to: "/briefs", label: "Forum-risk briefs", icon: ScrollText },
      { to: "/system-health", label: "System health", icon: FileCheck2 },
    ],
  },
];

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
}

export default function Sidebar({
  collapsed,
  onToggleCollapse,
}: SidebarProps) {
  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-40 flex flex-col overflow-hidden border-r border-[#a77b42]/20 bg-[radial-gradient(ellipse_at_10%_0%,rgba(167,123,66,0.16),transparent_36%),linear-gradient(180deg,#30251f_0%,#281f1b_100%)] text-[#f4e8d8] shadow-[8px_0_30px_rgba(30,15,0,0.14)] transition-[width] duration-200",
        collapsed ? "w-[76px]" : "w-[288px]",
      )}
    >
      <div
        className={cn(
          "relative flex min-h-[112px] items-center gap-3 border-b border-white/10 px-5",
          collapsed && "justify-center px-3",
        )}
      >
        <span
          className="relative grid h-12 w-12 shrink-0 place-items-center rounded-full border border-brass/70 text-brass-soft before:absolute before:inset-[4px] before:rounded-full before:border before:border-brass/30"
          aria-hidden="true"
        >
          <Scale size={20} strokeWidth={1.5} />
        </span>
        {!collapsed ? (
          <div className="min-w-0">
            <p className="font-editorial text-[17px] font-semibold leading-5 tracking-[0.1em] text-white">
              NYAAYCHAKRA
            </p>
            <p className="mt-1.5 flex items-center gap-1.5 text-[8px] font-bold uppercase tracking-[0.17em] text-brass-soft">
              <span className="h-px w-3 bg-brass/80" />
              The precedent desk
            </p>
          </div>
        ) : (
          <span className="sr-only">Nyaaychakra · The precedent desk</span>
        )}
        {!collapsed ? (
          <span className="absolute bottom-0 left-5 right-5 h-px bg-gradient-to-r from-brass/70 via-white/10 to-transparent" />
        ) : null}
      </div>

      <nav
        className="sidebar-navigation flex-1 space-y-5 overflow-y-auto px-3 py-5"
        aria-label="Main navigation"
      >
        {groups.map((group) => (
          <div key={group.label}>
            {!collapsed ? (
              <div className="mb-2 flex items-center gap-2 px-3">
                <span className="font-mono text-[9px] font-medium tracking-wide text-brass-soft/80">
                  {group.number}
                </span>
                <h2 className="text-[9px] font-bold uppercase tracking-[0.16em] text-white/45">
                  {group.label}
                </h2>
                <span className="h-px flex-1 bg-white/10" />
              </div>
            ) : (
              <div
                className="mx-auto mb-2 h-px w-7 bg-brass/35"
                aria-hidden="true"
              />
            )}
            <div className="space-y-1">
              {group.links.map(({ to, label, icon: Icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  title={collapsed ? label : undefined}
                  aria-label={collapsed ? label : undefined}
                  className={({ isActive }) =>
                    cn(
                      "group relative flex min-h-10 items-center gap-3 rounded-md border border-transparent px-3 text-[12px] transition-[background,color,border,transform] duration-150",
                      collapsed && "justify-center px-0",
                      isActive
                        ? "border-[#d5b27b]/20 bg-gradient-to-r from-[#f6ead7] to-[#ead9bf] font-semibold text-espresso shadow-[0_3px_12px_rgba(15,9,5,0.16)] before:absolute before:bottom-2 before:left-0 before:top-2 before:w-[3px] before:rounded-r before:bg-oxblood"
                        : "text-[#d6c3ba] hover:translate-x-0.5 hover:border-white/[0.06] hover:bg-white/[0.06] hover:text-white",
                    )
                  }
                >
                  <span className="grid h-7 w-7 shrink-0 place-items-center rounded-md transition-colors group-[.active]:bg-espresso/10 group-[.active]:text-oxblood">
                    <Icon size={16} strokeWidth={1.8} />
                  </span>
                  {!collapsed ? (
                    <>
                      <span className="flex-1">{label}</span>
                      <span className="h-1 w-1 rounded-full bg-brass-soft opacity-0 transition-opacity group-[.active]:opacity-100" />
                    </>
                  ) : null}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className={cn("border-t border-white/10 p-3", collapsed && "px-2")}>
        {!collapsed ? (
          <div className="rounded-md border border-brass/20 bg-[#211a16]/70 p-3">
            <div className="flex items-center gap-2">
              <span className="grid h-7 w-7 place-items-center rounded-md bg-brass/10 text-brass-soft">
                <Sparkles size={14} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[10px] font-semibold text-white/90">
                    Research workspace
                  </span>
                </div>
                <p className="mt-1 text-[9px] leading-4 text-white/45">
                  Live backend corpus
                </p>
              </div>
            </div>
          </div>
        ) : null}
        <NavLink
          to="/"
          title={collapsed ? "Exit to landing page" : undefined}
          aria-label="Exit to landing page"
          className={cn(
            "flex min-h-9 w-full items-center gap-3 rounded-md border border-[#d5b27b]/20 px-3 text-[11px] font-semibold text-brass-soft transition-colors hover:bg-white/10 hover:text-white",
            collapsed && "justify-center px-0",
          )}
        >
          <LogOut size={15} />
          {!collapsed ? <span>Exit workspace</span> : null}
        </NavLink>
        <button
          type="button"
          onClick={onToggleCollapse}
          className="mt-2 flex h-9 w-full items-center justify-center rounded-md text-white/45 transition-colors hover:bg-white/10 hover:text-brass-soft"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight size={17} /> : <ChevronLeft size={17} />}
        </button>
      </div>
    </aside>
  );
}
