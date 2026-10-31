import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { screenByPath } from "../data/screens";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

export default function AppShell() {
  const location = useLocation();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const title =
    screenByPath.get(location.pathname)?.title ??
    (location.pathname.startsWith("/judgment/") ? "Judgment viewer" : "Workspace");

  return (
    <div className="min-h-screen bg-parchment text-ink">
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed((value) => !value)}
      />
      <div
        className={`min-h-screen min-w-[760px] transition-[padding] duration-200 ${
          sidebarCollapsed ? "pl-[76px]" : "pl-[288px]"
        }`}
      >
        <Topbar title={title} />
        <main className="mx-auto w-full max-w-[1600px] px-8 py-8">
          <Outlet />
        </main>
        <footer className="px-8 pb-6 text-center text-[10px] leading-5 text-[#81756b]">
          <p>
            Backend records require primary-source verification and are not legal advice.
          </p>
        </footer>
      </div>
    </div>
  );
}
