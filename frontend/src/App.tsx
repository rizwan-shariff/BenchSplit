import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/AppShell";
import {
  BriefsPage,
  EvidencePage,
  EvaluationPage,
  IngestPage,
  InvestigationPage,
  JudgmentPage,
  LandingPage,
  NotFoundPage,
  OverviewPage,
  ProcessingPage,
  RadarPage,
  RunsPage,
  StatutesPage,
  SupremeCourtPage,
  SystemHealthPage,
} from "./pages/pages";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route element={<AppShell />}>
        <Route path="/overview" element={<OverviewPage />} />
        <Route path="/statutes" element={<StatutesPage />} />
        <Route path="/radar" element={<RadarPage />} />
        <Route path="/investigation" element={<InvestigationPage />} />
        <Route path="/evidence" element={<EvidencePage />} />
        <Route path="/supreme-court" element={<SupremeCourtPage />} />
        <Route path="/ingest" element={<IngestPage />} />
        <Route path="/processing" element={<ProcessingPage />} />
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/evaluation" element={<EvaluationPage />} />
        <Route path="/briefs" element={<BriefsPage />} />
        <Route path="/system-health" element={<SystemHealthPage />} />
        <Route path="/judgment/:propositionId" element={<JudgmentPage />} />
        <Route path="/not-found" element={<NotFoundPage />} />
        <Route path="*" element={<Navigate to="/not-found" replace />} />
      </Route>
    </Routes>
  );
}
